#!/usr/bin/env python3
"""
mini-proxy — HTTP/HTTPS CONNECT proxy, pure stdlib, untuk Termux.
Usage:
  python proxy.py [--port 8888] [--bind 0.0.0.0] [--auth user:pass]
Test dari device lain:
  curl -x http://IP_HP:8888 https://bebas.com
"""
import asyncio, base64, argparse, sys

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
