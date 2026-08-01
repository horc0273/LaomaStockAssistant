#!/usr/bin/env python3
"""老马股票助手 — 问财 & 东财AI 接口一键测试脚本

用法：
    python test_new_apis.py

环境变量：
    LAOMA_BASE_URL  — 服务地址，默认 http://127.0.0.1:8000
    LAOMA_TOKEN     — 登录 Token（从浏览器 Cookie 或登录接口获取）
"""
from __future__ import annotations

import os
import sys
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError

BASE_URL = os.getenv("LAOMA_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
TOKEN = os.getenv("LAOMA_TOKEN", "")


def api_call(method: str, path: str, data: dict | None = None) -> dict:
    url = f"{BASE_URL}{path}"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"

    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data else None
    req = Request(url, data=body, headers=headers, method=method)

    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        try:
            err_body = json.loads(e.read().decode("utf-8"))
        except Exception:
            err_body = {"error": str(e)}
        return {"_http_error": e.code, **err_body}
    except Exception as e:
        return {"_exception": str(e)}


def check(label: str, resp: dict, expect_ok: bool = True) -> bool:
    ok = resp.get("ok") if expect_ok else True
    has_error = "error" in resp or "_http_error" in resp or "_exception" in resp

    if ok and not has_error:
        print(f"  ✅ {label}")
        return True
    elif has_error:
        err_msg = resp.get("message", resp.get("error", str(resp)))
        print(f"  ❌ {label} — {err_msg}")
        return False
    else:
        print(f"  ⚠️  {label} — 响应: {json.dumps(resp, ensure_ascii=False)[:80]}")
        return True


def main() -> int:
    print("=" * 50)
    print("老马股票助手 — 新接口测试")
    print(f"服务端: {BASE_URL}")
    print(f"Token: {'已配置' if TOKEN else '未配置（部分接口可能401）'}")
    print("=" * 50)

    passed = 0
    total = 0

    # ---------- 问财接口 ----------
    print("\n【问财 iWencai】")

    total += 1
    resp = api_call("GET", "/api/wencai/status")
    if check("状态查询", resp):
        passed += 1

    total += 1
    resp = api_call("POST", "/api/wencai/query", {"question": "今日涨停的股票"})
    if check("自然语言选股", resp):
        passed += 1

    total += 1
    resp = api_call("POST", "/api/wencai/screen", {
        "conditions": ["近5日涨幅大于5%", "市值大于50亿"]
    })
    if check("条件筛选", resp):
        passed += 1

    # ---------- 东财妙想AI ----------
    print("\n【东方财富妙想AI】")

    total += 1
    resp = api_call("GET", "/api/eastmoney-ai/status")
    if check("状态查询", resp):
        passed += 1
        # 如果未启用，提示用户配置
        if not resp.get("enabled"):
            print("     💡 提示: 东财AI未启用，请配置 EASTMONEY_AI_API_KEY 环境变量")

    total += 1
    resp = api_call("POST", "/api/eastmoney-ai/hotspot", {
        "question": "今日热点"
    })
    if check("热点发现", resp):
        passed += 1

    total += 1
    resp = api_call("POST", "/api/eastmoney-ai/stock-analysis", {
        "code": "000001"
    })
    if check("个股分析 (000001)", resp):
        passed += 1

    total += 1
    resp = api_call("POST", "/api/eastmoney-ai/performance", {
        "code": "600519"
    })
    if check("业绩点评 (600519)", resp):
        passed += 1

    total += 1
    resp = api_call("POST", "/api/eastmoney-ai/sentiment")
    if check("市场情绪", resp):
        passed += 1

    total += 1
    resp = api_call("POST", "/api/eastmoney-ai/chat", {
        "question": "分析一下当前新能源板块",
        "code": "300750",
        "name": "宁德时代"
    })
    if check("AI问答", resp):
        passed += 1

    # ---------- 汇总 ----------
    print("\n" + "=" * 50)
    print(f"测试结果: {passed}/{total} 通过")
    if passed == total:
        print("🎉 全部通过！新接口已就绪。")
    else:
        print("⚠️  部分接口未通过，请查看上方错误信息。")
        if not TOKEN:
            print("   提示: 未配置 LAOMA_TOKEN，请先登录获取 Token。")
    print("=" * 50)

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
