from __future__ import annotations

from datetime import datetime
from typing import Any


class IndustryChainService:
    TOPIC_TEMPLATES = {
        "ai": {
            "aliases": ["ai", "算力", "服务器", "cpo", "液冷", "pcb", "人工智能"],
            "topic": "AI算力",
            "chain": [
                {"layer": "上游", "items": ["铜箔", "覆铜板", "高速连接器", "光模块"]},
                {"layer": "中游", "items": ["PCB", "液冷", "电源", "AI服务器"]},
                {"layer": "下游", "items": ["云厂商", "数据中心", "大模型训练"]},
            ],
            "bottlenecks": [
                {"name": "高端PCB产能", "reason": "AI服务器升级带来层数、材料和良率要求提升"},
                {"name": "液冷散热", "reason": "高功耗芯片推动散热方案升级"},
            ],
            "seed_stocks": {
                "002463.SZ": "高端PCB",
                "300476.SZ": "高端PCB",
                "600183.SH": "覆铜板/材料",
                "601138.SH": "AI服务器",
                "300308.SZ": "光模块",
                "300502.SZ": "光模块",
            },
        },
        "power": {
            "aliases": ["电力", "电网", "特高压", "电力设备"],
            "topic": "电力设备",
            "chain": [
                {"layer": "上游", "items": ["铜", "绝缘材料", "电力电子元件"]},
                {"layer": "中游", "items": ["变压器", "开关设备", "储能 PCS"]},
                {"layer": "下游", "items": ["电网投资", "数据中心供电", "新能源并网"]},
            ],
            "bottlenecks": [
                {"name": "电网扩容", "reason": "新能源和数据中心需求提升电网侧投资强度"},
            ],
            "seed_stocks": {
                "600900.SH": "电力运营",
                "600312.SH": "特高压设备",
                "300750.SZ": "储能与电池",
            },
        },
        "resource": {
            "aliases": ["铜", "黄金", "资源", "有色"],
            "topic": "资源金属",
            "chain": [
                {"layer": "上游", "items": ["矿山", "冶炼", "加工"]},
                {"layer": "中游", "items": ["铜材", "贵金属", "资源综合利用"]},
                {"layer": "下游", "items": ["电力设备", "新能源", "电子制造"]},
            ],
            "bottlenecks": [
                {"name": "资源价格弹性", "reason": "商品价格变化会放大利润和估值波动"},
            ],
            "seed_stocks": {
                "000737.SZ": "铜资源",
                "000630.SZ": "铜冶炼",
                "601899.SH": "黄金/铜矿",
            },
        },
    }

    def catalog(self) -> dict:
        return {"topics": [{"key": key, "name": value["topic"], "aliases": value["aliases"]} for key, value in self.TOPIC_TEMPLATES.items()]}

    def analyze(self, topic: str, universe: list[dict] | None = None, mode: str = "quick") -> dict:
        template = self._template_for(topic)
        candidates = self._candidates(template, universe or [])
        return {
            "topic": topic or template["topic"],
            "normalized_topic": template["topic"],
            "mode": mode,
            "summary": f"{template['topic']}按上中下游拆解，优先关注卡点环节与有行情、资金或明确产业链角色的候选公司。",
            "chain": template["chain"],
            "chain_nodes": [f"{item['layer']}：{'、'.join(item['items'])}" for item in template["chain"]],
            "bottlenecks": template["bottlenecks"],
            "candidates": candidates,
            "evidence": self._evidence(candidates),
            "risks": ["数据源可能延迟", "概念相关不等于主营收入占比", "需结合公告、研报和财报继续核实"],
            "disclaimer": "产业链研究用于缩小研究范围；缺失数据需验证，不构成交易建议。",
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }

    def analyze_stock(self, code: str, universe: list[dict] | None = None) -> dict:
        rows = universe or []
        stock = next((item for item in rows if str(item.get("code", "")).lower() == code.lower()), None)
        if not stock:
            return {"stock": {"code": code, "chain_role": "数据未返回/需核实"}, "reports": []}
        topic_seed = " ".join([str(stock.get("industry") or ""), " ".join(stock.get("concepts") or []), str(stock.get("tag") or "")])
        report = self.analyze(topic_seed, rows)
        role = next((item.get("role") for item in report["candidates"] if item.get("code") == stock.get("code")), "需结合主营核实")
        return {"stock": {"code": stock.get("code"), "name": stock.get("name"), "chain_role": role}, "reports": [report]}

    def _template_for(self, topic: str) -> dict:
        haystack = (topic or "").lower()
        for template in self.TOPIC_TEMPLATES.values():
            if any(alias.lower() in haystack for alias in template["aliases"]):
                return template
        return self.TOPIC_TEMPLATES["ai"]

    def _candidates(self, template: dict, universe: list[dict[str, Any]]) -> list[dict]:
        aliases = {alias.lower() for alias in template["aliases"]}
        seed_stocks = template.get("seed_stocks") or {}
        result = []
        for row in universe:
            code = str(row.get("code") or "")
            text = " ".join([
                str(row.get("name") or ""),
                str(row.get("industry") or ""),
                str(row.get("tag") or ""),
                " ".join(str(item) for item in (row.get("concepts") or [])),
            ]).lower()
            seeded_role = seed_stocks.get(code)
            if not seeded_role and not any(alias in text for alias in aliases):
                continue
            evidence_score = 40
            if seeded_role:
                evidence_score += 20
            if row.get("concepts"):
                evidence_score += 15
            if float(row.get("amount") or 0) >= 500_000_000:
                evidence_score += 15
            if float(row.get("main_net") or 0) > 0:
                evidence_score += 10
            if row.get("signals"):
                evidence_score += 10
            evidence_score = min(95, evidence_score)
            result.append({
                "code": code,
                "name": row.get("name", ""),
                "role": seeded_role or self._role_for(row, template),
                "evidence_score": evidence_score,
                "score": evidence_score,
                "priority": "高" if evidence_score >= 75 else "中" if evidence_score >= 55 else "低",
                "evidence": [
                    *(["产业链种子股匹配"] if seeded_role else []),
                    *(["概念字段匹配"] if row.get("concepts") else []),
                    *(["成交活跃"] if float(row.get("amount") or 0) >= 500_000_000 else []),
                    *(["主力净流入"] if float(row.get("main_net") or 0) > 0 else []),
                ],
                "risks": ["估值和订单节奏需验证", "概念热度可能回落"],
            })
        result.sort(key=lambda item: item["evidence_score"], reverse=True)
        return result[:20]

    @staticmethod
    def _role_for(row: dict, template: dict) -> str:
        text = " ".join([str(row.get("industry") or ""), str(row.get("tag") or ""), " ".join(row.get("concepts") or [])])
        if "PCB" in text or "pcb" in text.lower():
            return "高端PCB"
        if "液冷" in text:
            return "液冷散热"
        if "电力" in text:
            return "电力设备"
        if "铜" in text or "资源" in text:
            return "资源上游"
        return template["chain"][1]["items"][0]

    @staticmethod
    def _evidence(candidates: list[dict]) -> list[dict]:
        return [{"code": item["code"], "source_type": "行情/概念/资金", "summary": f"{item['name']} 产业链角色：{item['role']}，证据分 {item['evidence_score']}"} for item in candidates[:8]]
