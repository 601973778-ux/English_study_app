#!/usr/bin/env python3
"""
在 English_study_app 根目录启动静态服务，供 milestone1/index.html 通过 fetch 读取词表。
用法: 在本目录执行  python serve_milestone1.py
然后浏览器打开输出的地址，进入 /milestone1/index.html
"""

from __future__ import annotations

import http.server
import os
import socketserver
import webbrowser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8765


def main() -> None:
    os.chdir(ROOT)
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", PORT), handler) as httpd:
        url = f"http://127.0.0.1:{PORT}/milestone1/index.html"
        print(f"Serving {ROOT}")
        print(f"Open: {url}")
        print("Ctrl+C to stop.")
        try:
            webbrowser.open(url)
        except OSError:
            pass
        httpd.serve_forever()


if __name__ == "__main__":
    main()
