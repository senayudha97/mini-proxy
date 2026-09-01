#!/usr/bin/env python3
"""
mini-proxy — HTTP/HTTPS CONNECT proxy + app launcher home, pure stdlib, untuk Termux.
Usage:
  python proxy.py [--port 8888] [--bind 0.0.0.0] [--auth user:pass]
Home page (buka IP:port langsung di browser) = daftar shortcut apps.
"""
import asyncio, base64, argparse, sys

# ==== APPS LIST — edit di sini ====
APPS = [
    # (nama,         URL tujuan,                             catatan/login)
    ("Hermes Dashboard", "https://hermes.owl-labs.online",   "user: hermes"),
    ("Portfolio Tracker", "https://portfolio.owl-labs.online", "login: sena"),
    ("Docs Viewer", "https://docs.owl-labs.online",          "tanpa login"),
    ("Loan Simulator", "https://loansimulator.owl-labs.online", "tanpa login"),
    ("App Center", "https://app.owl-labs.online",            "lihat password di config"),
    ("9router", "https://heads-badge-watched-asia.trycloudflare.com", "API router — ephemeral URL"),
]
# ==================================

HOME_HTML = """<!DOCTYPE html>
<html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>mini-proxy — apps</title>
<style>
  :root{--bg:#000;--fg:#fff;--dim:#9a9a9a;--line:#1c1c1c;--acc:#00ff66}
  body{margin:0;font-family:'Share Tech Mono',ui-monospace,monospace;background:var(--bg);
    color:var(--fg);min-height:100vh;display:flex;flex-direction:column;align-items:center;
    -webkit-font-smoothing:none;letter-spacing:.02em}
  .wrap{width:min(680px,92vw);padding:48px 0 64px}
  h1{font-size:1.1rem;font-weight:400;letter-spacing:.3em;text-transform:uppercase;
    color:var(--dim);border-bottom:1px solid var(--line);padding-bottom:14px;margin:0 0 8px}
  .sub{font-size:.75rem;color:var(--dim);margin-bottom:28px}
  a.app{display:flex;justify-content:space-between;align-items:center;gap:12px;
    text-decoration:none;color:var(--fg);border:1px solid var(--line);
    padding:16px 18px;margin-bottom:10px;font-size:.95rem;background:transparent}
  a.app:hover{border-color:var(--acc);text-shadow:0 0 6px rgba(0,255,102,.4)}
  .note{font-size:.7rem;color:var(--dim);letter-spacing:.05em}
  .foot{font-size:.65rem;color:#555;margin-top:26px;text-align:center}
</style></head><body><div class="wrap">
<h1>&#129417; owl-labs // apps</h1>
<div class="sub">proxy aktif &#183; klik buka tab baru</div>
%%ITEMS%%
<div class="foot">mini-proxy v1.1 &#183; edit daftar di proxy.py (APPS)</div>
</div></body></html>"""

def render_home():
    items = []
    for name, url, note in APPS:
        items.append(
            f'<a class="app" href="{url}" target="_blank" rel="noopener">'
            f'<span>{name}</span><span class="note">{note}</span></a>')
    return HOME_HTML.replace("%%ITEMS%%", "\n".join(items))

async def pipe(reader, writer):
    try:
        while True:
            data = await reader.read(65536)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except Exception:
        pass
    finally:
        try:
            writer.close()
        except Exception:
            pass

def check_auth(headers, auth):
    if not auth:
        return True
    val = headers.get("proxy-authorization", "")
    if not val.startswith("Basic "):
        return False
    try:
        got = base64.b64decode(val[6:]).decode()
    except Exception:
        return False
    return got == auth

async def handle(client_r, client_w, auth):
    try:
        line = await asyncio.wait_for(client_r.readline(), timeout=30)
        headers = {}
        while True:
            h = await asyncio.wait_for(client_r.readline(), timeout=10)
            if h in (b"\r\n", b"\n", b""):
                break
            if b":" in h:
                k, v = h.split(b":", 1)
                headers[k.decode().strip().lower()] = v.decode().strip()
        parts = line.decode(errors="replace").split()
        if len(parts) < 3:
            client_w.close(); return
        method, target, ver = parts[0], parts[1], parts[2]
        # home page: GET origin-form (bukan absolute URL) → tampilkan launcher
        if method == "GET" and not target.startswith("http"):
            body = render_home().encode()
            client_w.write(b"HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\n"
                           b"Cache-Control: no-store\r\nContent-Length: "
                           + str(len(body)).encode() + b"\r\n\r\n" + body)
            await client_w.drain(); client_w.close(); return
        if not check_auth(headers, auth):
            client_w.write(b"HTTP/1.1 407 Proxy Authentication Required\r\n"
                           b"Proxy-Authenticate: Basic realm=\"proxy\"\r\nContent-Length: 0\r\n\r\n")
            await client_w.drain(); client_w.close(); return
        if method == "CONNECT":
            host, _, port = target.partition(":")
            port = int(port or 443)
            try:
                up_r, up_w = await asyncio.wait_for(
                    asyncio.open_connection(host, port), timeout=15)
            except Exception:
                client_w.write(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n")
                await client_w.drain(); client_w.close(); return
            client_w.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            await client_w.drain()
            await asyncio.gather(pipe(client_r, up_w), pipe(up_r, client_w))
        elif method in ("GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS", "PATCH"):
            # absolute-form: http://host/path via proxy
            from urllib.parse import urlsplit
            u = urlsplit(target)
            host, port = u.hostname, u.port or 80
            path = u.path or "/"
            if u.query: path += "?" + u.query
            try:
                up_r, up_w = await asyncio.wait_for(
                    asyncio.open_connection(host, port), timeout=15)
            except Exception:
                client_w.write(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n")
                await client_w.drain(); client_w.close(); return
            hh = {k: v for k, v in headers.items() if k not in ("proxy-connection", "proxy-authorization")}
            req = f"{method} {path} {ver}\r\n" + "".join(f"{k}: {v}\r\n" for k, v in hh.items()) + "\r\n"
            up_w.write(req.encode()); await up_w.drain()
            await asyncio.gather(pipe(client_r, up_w), pipe(up_r, client_w))
        else:
            client_w.write(b"HTTP/1.1 405 Method Not Allowed\r\nContent-Length: 0\r\n\r\n")
            await client_w.drain(); client_w.close()
    except Exception as e:
        print(f"[err] {e}", file=sys.stderr)
    finally:
        try:
            client_w.close()
        except Exception:
            pass

async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8888)
    ap.add_argument("--bind", default="0.0.0.0")
    ap.add_argument("--auth", default=None, help="user:pass (disarankan di hotspot)")
    a = ap.parse_args()
    auth = a.auth or None
    server = await asyncio.start_server(
        lambda r, w: handle(r, w, auth), a.bind, a.port)
    print(f"mini-proxy listening {a.bind}:{a.port} auth={'ON' if auth else 'OFF'}")
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("bye")
