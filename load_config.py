"""配置加载器 - 启动服务前自动加载环境变量。

用法:
    python load_config.py
    python load_config.py --start  # 加载配置并启动服务

支持加载源（优先级从高到低）:
    1. 系统环境变量（已存在的不覆盖）
    2. .env 文件（如果用户手动创建）
    3. 各服务的 token 文件（wencai_hexinv.txt 等）
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent


def load_env_file(filepath: Path) -> dict[str, str]:
    """加载 .env 文件，返回 key-value 字典。"""
    config: dict[str, str] = {}
    if not filepath.exists():
        return config
    with open(filepath, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and value and not value.startswith("your_"):
                config[key] = value
    return config


def load_token_file(filepath: Path) -> str:
    """加载单值 token 文件。"""
    if filepath.exists():
        return filepath.read_text(encoding="utf-8").strip()
    return ""


def main() -> None:
    """加载所有配置到环境变量。"""
    loaded: list[str] = []

    # 1. 加载 .env 文件（如果用户创建了）
    env_file = ROOT / ".env"
    if env_file.exists():
        for key, value in load_env_file(env_file).items():
            if not os.getenv(key):
                os.environ[key] = value
                loaded.append(f"{key}=... (from .env)")

    # 2. 加载问财 hexin-v（从文件）
    hexinv_file = ROOT / "wencai_hexinv.txt"
    hexinv = load_token_file(hexinv_file)
    if hexinv and not os.getenv("IWENCAI_HEXINV"):
        os.environ["IWENCAI_HEXINV"] = hexinv
        loaded.append("IWENCAI_HEXINV=... (from wencai_hexinv.txt)")

    # 3. 加载东财 key（从文件）
    em_key_file = ROOT / "eastmoney_api_key.txt"
    em_key = load_token_file(em_key_file)
    if em_key and not os.getenv("EASTMONEY_AI_API_KEY"):
        os.environ["EASTMONEY_AI_API_KEY"] = em_key
        loaded.append("EASTMONEY_AI_API_KEY=... (from eastmoney_api_key.txt)")

    em_cookie_file = ROOT / "eastmoney_cookie.txt"
    em_cookie = load_token_file(em_cookie_file)
    if em_cookie and not os.getenv("EASTMONEY_QGQP_B_ID"):
        os.environ["EASTMONEY_QGQP_B_ID"] = em_cookie
        loaded.append("EASTMONEY_QGQP_B_ID=... (from eastmoney_cookie.txt)")

    if loaded:
        print("[load_config] 已加载配置:")
        for item in loaded:
            print(f"  ✓ {item}")
    else:
        print("[load_config] 无可加载的新配置（环境变量已存在或文件不存在）")

    # 如果传了 --start，启动 uvicorn
    if "--start" in sys.argv:
        print("\n[load_config] 正在启动 uvicorn...")
        os.chdir(ROOT / "app")
        os.system(f'{sys.executable} -m uvicorn main:app --reload --host 0.0.0.0 --port 8000')


if __name__ == "__main__":
    main()
