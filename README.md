# mini-proxy

HTTP/HTTPS CONNECT proxy — pure Python stdlib, zero dependency. Dibuat
untuk jalan di Termux (Android) sebagai pivot: device lain browsing
lewat koneksi HP.

## Install (Termux)

```bash
pkg update -y && pkg install python -y
git clone https://github.com/senayudha97/mini-proxy.git
python mini-proxy/proxy.py --port 8888 --auth user:pass
```

## Pakai

1. HP: aktifkan hotspot, jalankan proxy (command di atas)
2. Cek IP HP: `ifconfig wlan0` di Termux (default hotspot Android: 192.168.43.1)
3. Device lain: set HTTP proxy manual = `IP_HP:8888` + user/pass
4. Firefox: Settings → Network Settings → Manual Proxy Configuration

## Fitur

- CONNECT tunneling (HTTPS) + absolute-form (HTTP)
- Basic auth opsional (`--auth user:pass`)
- Force TCP (no QUIC/HTTP3) — berguna buat network yang blok format QUIC
- Zero dependency: cuma Python 3 stdlib (asyncio)

## Usage

```
python proxy.py [--port 8888] [--bind 0.0.0.0] [--auth user:pass]
```
