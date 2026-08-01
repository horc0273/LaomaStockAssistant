from __future__ import annotations


class RecommendationScoringService:
    def score(self, stock: dict, abnormal_events: list[dict] | None = None, industry_chain_report: dict | None = None, ai_review: dict | None = None) -> dict:
        events = [item for item in (abnormal_events or []) if item.get("code") == stock.get("code")]
        candidates = (industry_chain_report or {}).get("candidates") or []
        chain_candidate = next((item for item in candidates if item.get("code") == stock.get("code")), None)

        data_quality = 10
        abnormal = min(20, len(events) * 8)
        technical = min(20, len(stock.get("signals") or []) * 5)
        fund = 0
        main_net = float(stock.get("main_net") or 0)
        amount = float(stock.get("amount") or 0)
        if main_net > 0:
            fund += 8
        if main_net >= 100_000_000:
            fund += 6
        if amount >= 500_000_000:
            fund += 6
        industry_chain = min(20, int((chain_candidate or {}).get("evidence_score", 0) / 5)) if chain_candidate else 0
        ai = int(ai_review.get("score", 0)) if ai_review else 0
        risk_penalty = 0
        if float(stock.get("change_pct") or 0) >= 9.8:
            risk_penalty += 5
        if main_net < 0:
            risk_penalty += 8

        total = max(0, min(100, data_quality + abnormal + technical + fund + industry_chain + ai - risk_penalty))
        if total >= 78:
            level = "强观察"
        elif total >= 60:
            level = "观察"
        elif total >= 45:
            level = "等确认"
        else:
            level = "风险升高"
        return {
            "code": stock.get("code"),
            "name": stock.get("name"),
            "total_score": total,
            "level": level,
            "components": {
                "data_quality": data_quality,
                "abnormal": abnormal,
                "technical": technical,
                "fund": fund,
                "industry_chain": industry_chain,
                "ai_review": ai,
                "risk_penalty": risk_penalty,
            },
            "evidence": [item.get("type") for item in events[:5]] + ([f"产业链：{chain_candidate.get('role')}"] if chain_candidate else []),
            "risk_note": "高位或资金分歧时只做观察，必须等待触发条件和失效价确认。",
        }
