from __future__ import annotations

import os
import socket
import threading
import time
import traceback
import urllib.request
import webbrowser
from pathlib import Path

import uvicorn


MUTEX_NAME = "LaomaStockAssistant.Singleton"
_mutex_handle = None
_AUTO_LAN_IP = object()


def app_data_dir() -> Path:
    base = os.getenv("APPDATA") or str(Path.home())
    path = Path(base) / "LaomaStockAssistant"
    path.mkdir(parents=True, exist_ok=True)
    return path


def choose_port(preferred: int = 8788) -> int:
    for port in range(preferred, preferred + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.2)
            if sock.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return preferred


def local_app_url(port: int) -> str:
    return f"http://127.0.0.1:{port}/?v=desktop-exe"


def detect_lan_ip() -> str | None:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        return None
    return None


def public_app_url(port: int, bind_host: str = "0.0.0.0", lan_ip: str | None | object = _AUTO_LAN_IP) -> str:
    if bind_host not in {"0.0.0.0", "::"}:
        return local_app_url(port)
    candidate = detect_lan_ip() if lan_ip is _AUTO_LAN_IP else lan_ip
    if candidate:
        return f"http://{candidate}:{port}/?v=desktop-exe"
    return local_app_url(port)


def existing_app_url(port: int = 8788) -> str | None:
    url = local_app_url(port)
    try:
        with urllib.request.urlopen(url, timeout=0.8) as response:
            body = response.read(8192).decode("utf-8", errors="ignore")
        if response.status == 200 and "老马智能股票盯盘助手" in body:
            return url
    except Exception:
        return None
    return None


def acquire_single_instance() -> bool:
    global _mutex_handle
    try:
        import ctypes

        _mutex_handle = ctypes.windll.kernel32.CreateMutexW(None, False, MUTEX_NAME)
        return ctypes.windll.kernel32.GetLastError() != 183
    except Exception:
        return True


def open_browser_later(url: str) -> None:
    def _open() -> None:
        time.sleep(1.5)
        webbrowser.open(url)

    threading.Thread(target=_open, daemon=True).start()


def main() -> None:
    data_dir = app_data_dir()
    os.environ.setdefault("LAOMA_STOCK_DATA_DIR", str(data_dir))
    os.environ.setdefault("PYTHONUTF8", "1")
    if not acquire_single_instance():
        webbrowser.open(existing_app_url() or local_app_url(8788))
        return
    existing_url = existing_app_url()
    if existing_url:
        webbrowser.open(existing_url)
        return
    try:
        port = choose_port()
        bind_host = os.getenv("LAOMA_BIND_HOST", "0.0.0.0").strip() or "0.0.0.0"
        open_browser_later(local_app_url(port))
        lan_url = public_app_url(port, bind_host=bind_host)
        print(f"LaomaStockAssistant running on {local_app_url(port)}")
        if lan_url != local_app_url(port):
            print(f"LAN access available at {lan_url}")
        uvicorn.run(
            "app.main:app",
            host=bind_host,
            port=port,
            log_config=None,
            access_log=False,
        )
    except Exception:
        error_path = data_dir / "startup-error.log"
        error_path.write_text(traceback.format_exc(), encoding="utf-8")
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(
                0,
                f"软件启动失败。错误日志：\n{error_path}",
                "老马智能股票盯盘助手",
                0x10,
            )
        except Exception:
            pass


if __name__ == "__main__":
    main()
