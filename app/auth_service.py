from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
from datetime import datetime, timedelta
from math import ceil
from pathlib import Path


DEFAULT_TRIAL_DAYS = 14

MEMBERSHIP_TIERS = [
    {
        "id": "trial",
        "name": "试用会员",
        "badge": "14天试用",
        "price_month": 0,
        "price_year": 0,
        "audience": "朋友试用、临时体验",
        "description": "保留核心盯盘能力，限制高成本的AI、回测和模拟盘次数。",
        "features": {
            "watchlist": True,
            "basic_quotes": True,
            "mobile_view": True,
            "personal_ai_key": True,
            "basic_ai_report": True,
            "advanced_quant_radar": False,
            "ea_simulation": "limited",
            "backtest": "limited",
            "news_sync_24h": False,
            "admin_console": False,
        },
        "limits": {"watchlist": 20, "ai_reports_per_day": 3, "ea_runs_per_day": 3, "backtest_years": 1},
        "benefits": ["14天试用", "基础自选与行情", "手机端查看", "少量AI分析与EA模拟"],
    },
    {
        "id": "supporter",
        "name": "赞助会员",
        "badge": "基础全功能",
        "price_month": 9.9,
        "price_year": 99,
        "audience": "长期自用、朋友低门槛赞助",
        "description": "适合大多数朋友使用，重点是自备AI Key、手机盯盘和基础策略验证。",
        "features": {
            "watchlist": True,
            "basic_quotes": True,
            "mobile_view": True,
            "personal_ai_key": True,
            "basic_ai_report": True,
            "advanced_quant_radar": False,
            "ea_simulation": True,
            "backtest": True,
            "news_sync_24h": False,
            "admin_console": False,
        },
        "limits": {"watchlist": 80, "ai_reports_per_day": 20, "ea_runs_per_day": 20, "backtest_years": 3},
        "benefits": ["基础全功能", "自备AI模型Key", "更多AI分析次数", "基础EA模拟盘", "基础回测验证"],
    },
    {
        "id": "pro",
        "name": "进阶赞助会员",
        "badge": "量化增强",
        "price_month": 19.9,
        "price_year": 199,
        "audience": "需要深度盯盘、复盘和策略验证的用户",
        "description": "解锁量化雷达3.0、深度资金/K线/分时联动和更多历史验证能力。",
        "features": {
            "watchlist": True,
            "basic_quotes": True,
            "mobile_view": True,
            "personal_ai_key": True,
            "basic_ai_report": True,
            "advanced_quant_radar": True,
            "ea_simulation": True,
            "backtest": True,
            "news_sync_24h": True,
            "admin_console": False,
        },
        "limits": {"watchlist": 200, "ai_reports_per_day": 80, "ea_runs_per_day": 80, "backtest_years": 5},
        "benefits": ["量化雷达3.0", "K线/资金/分时综合分析", "24h资讯同步", "更多EA模拟与回测次数", "自动复盘报告"],
    },
    {
        "id": "sponsor",
        "name": "共建赞助会员",
        "badge": "优先共建",
        "price_month": 29.9,
        "price_year": 299,
        "audience": "愿意一起共建策略和功能的深度用户",
        "description": "适合需要优先体验、策略模板和部署配置支持的朋友。",
        "features": {
            "watchlist": True,
            "basic_quotes": True,
            "mobile_view": True,
            "personal_ai_key": True,
            "basic_ai_report": True,
            "advanced_quant_radar": True,
            "ea_simulation": True,
            "backtest": True,
            "news_sync_24h": True,
            "priority_support": True,
            "admin_console": False,
        },
        "limits": {"watchlist": 500, "ai_reports_per_day": 200, "ea_runs_per_day": 200, "backtest_years": 10},
        "benefits": ["进阶全部权益", "优先体验新功能", "策略模板库", "部署/配置支持", "共建需求优先排期"],
    },
    {
        "id": "founder",
        "name": "创始管理员",
        "badge": "全部功能",
        "price_month": 0,
        "price_year": 0,
        "audience": "系统管理员",
        "description": "管理员专用，拥有会员管理、系统AI配置、数据源配置和全部功能。",
        "features": {
            "watchlist": True,
            "basic_quotes": True,
            "mobile_view": True,
            "personal_ai_key": True,
            "basic_ai_report": True,
            "advanced_quant_radar": True,
            "ea_simulation": True,
            "backtest": True,
            "news_sync_24h": True,
            "priority_support": True,
            "admin_console": True,
        },
        "limits": {"watchlist": -1, "ai_reports_per_day": -1, "ea_runs_per_day": -1, "backtest_years": -1},
        "benefits": ["全部功能", "会员管理", "系统AI配置", "Tushare与数据源管理", "内部部署管理"],
    },
]

MEMBERSHIP_TIER_BY_ID = {tier["id"]: tier for tier in MEMBERSHIP_TIERS}


def membership_plan_catalog() -> dict:
    return {
        "philosophy": "低门槛赞助制：免费试用能看清价值，付费解锁高成本能力；收费只对应软件服务、数据能力和功能权限，不承诺收益。",
        "default_trial_days": DEFAULT_TRIAL_DAYS,
        "private_contact": {
            "enabled": True,
            "name": "苏元将",
            "location": "湖南·长沙",
            "qr_path": "/static/private-contact-qr.png",
            "title": "首批名额采用人工审核与私域开通",
            "description": "扫码添加微信，说明手机号和想体验的套餐；管理员确认后开通或续期。暂不开放公开自助付费。",
        },
        "admin_activation": True,
        "tiers": MEMBERSHIP_TIERS,
        "free_features": ["基础自选", "基础行情", "手机端查看", "少量AI分析", "少量EA模拟"],
        "paid_features": ["个人AI Key", "更多分析次数", "量化雷达3.0", "24h资讯同步", "深度回测验证", "策略模板与部署支持"],
        "rules": [
            "AI分析结果仅供研究参考，不构成投资建议，不承诺收益。",
            "普通会员默认使用自己的大模型API Key，避免消耗管理员额度。",
            "真实交易默认关闭；自动操作必须先经过模拟盘、预检、冷静期和人工确认。",
            "第一版采用管理员手动开通/续期，后续再接微信/支付宝订单。",
        ],
    }


def membership_summary(plan: str, expires_at: str | None) -> dict:
    tier = MEMBERSHIP_TIER_BY_ID.get(plan or "trial", MEMBERSHIP_TIER_BY_ID["trial"])
    days_remaining = None
    status = "long_term"
    if expires_at:
        try:
            expires = datetime.fromisoformat(expires_at)
            remaining_seconds = (expires - datetime.now()).total_seconds()
            days_remaining = max(0, ceil(remaining_seconds / 86400))
            status = "active" if remaining_seconds >= 0 else "expired"
        except ValueError:
            status = "unknown"
    return {
        "tier_id": tier["id"],
        "tier_name": tier["name"],
        "badge": tier["badge"],
        "expires_at": expires_at,
        "days_remaining": days_remaining,
        "status": status,
        "features": tier["features"],
        "limits": tier["limits"],
    }


class AuthService:
    def __init__(self, data_dir: Path) -> None:
        self.db_path = data_dir / "auth.sqlite"
        data_dir.mkdir(parents=True, exist_ok=True)
        self.init_db()
        self.ensure_default_admin()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                create table if not exists users (
                    id integer primary key autoincrement,
                    username text unique not null,
                    phone text unique,
                    password_hash text not null,
                    salt text not null,
                    display_name text not null,
                    role text not null default 'member',
                    plan text not null default 'trial',
                    expires_at text,
                    is_active integer not null default 1,
                    created_at text not null
                )
                """
            )
            columns = {row["name"] for row in conn.execute("pragma table_info(users)").fetchall()}
            if "phone" not in columns:
                conn.execute("alter table users add column phone text")
            conn.execute("create unique index if not exists idx_users_phone on users(phone) where phone is not null")
            conn.execute(
                """
                create table if not exists sessions (
                    token text primary key,
                    user_id integer not null,
                    expires_at text not null,
                    created_at text not null
                )
                """
            )

    def ensure_default_admin(self) -> None:
        username = os.getenv("LAOMA_ADMIN_USER", "laoma")
        password = os.getenv("LAOMA_ADMIN_PASSWORD", "maguo591034")
        if os.getenv("INTERNAL_DEPLOYMENT") == "1" and password == "maguo591034":
            raise RuntimeError("内部部署必须通过 LAOMA_ADMIN_PASSWORD 设置新的管理员密码")
        with self.connect() as conn:
            exists = conn.execute("select id from users where username = ?", (username,)).fetchone()
            if exists:
                return
            salt = secrets.token_hex(16)
            conn.execute(
                """
                insert into users (username, password_hash, salt, display_name, role, plan, expires_at, is_active, created_at)
                values (?, ?, ?, ?, ?, ?, ?, 1, ?)
                """,
                (
                    username,
                    self.hash_password(password, salt),
                    salt,
                    "老马管理员",
                    "admin",
                    "founder",
                    (datetime.now() + timedelta(days=3650)).isoformat(timespec="seconds"),
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )

    def create_user(
        self,
        username: str,
        password: str,
        display_name: str = "",
        phone: str = "",
        role: str = "member",
        plan: str = "trial",
        days: int = 30,
    ) -> dict:
        username = username.strip()
        phone = phone.strip()
        if not username or not password:
            return {"error": "missing_required"}
        if role not in {"admin", "analyst", "member", "viewer"}:
            return {"error": "invalid_role"}
        salt = secrets.token_hex(16)
        expires_at = (datetime.now() + timedelta(days=days)).isoformat(timespec="seconds") if days > 0 else None
        with self.connect() as conn:
            try:
                conn.execute(
                    """
                    insert into users (username, phone, password_hash, salt, display_name, role, plan, expires_at, is_active, created_at)
                    values (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                    """,
                    (
                        username,
                        phone or None,
                        self.hash_password(password, salt),
                        salt,
                        display_name or username,
                        role,
                        plan,
                        expires_at,
                        datetime.now().isoformat(timespec="seconds"),
                    ),
                )
            except sqlite3.IntegrityError:
                return {"error": "username_exists"}
            row = conn.execute("select * from users where username = ?", (username,)).fetchone()
            return {"ok": True, "user": self.public_user(row)}

    def register_by_phone(self, phone: str, password: str, display_name: str = "") -> dict:
        phone = "".join(ch for ch in phone.strip() if ch.isdigit())
        if len(phone) != 11 or not phone.startswith("1"):
            return {"error": "invalid_phone", "message": "请输入有效的11位手机号"}
        if len(password or "") < 6:
            return {"error": "weak_password", "message": "密码至少需要6位"}
        return self.create_user(
            phone,
            password,
            display_name=display_name or f"手机用户{phone[-4:]}",
            phone=phone,
            role="member",
            plan="trial",
            days=DEFAULT_TRIAL_DAYS,
        )

    def list_users(self) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute("select * from users order by id").fetchall()
            return [self.public_user(row) for row in rows]

    def update_user(
        self,
        user_id: int,
        *,
        display_name: str | None = None,
        phone: str | None = None,
        role: str | None = None,
        plan: str | None = None,
        days: int | None = None,
        is_active: bool | None = None,
        password: str | None = None,
    ) -> dict:
        if role and role not in {"admin", "analyst", "member", "viewer"}:
            return {"error": "invalid_role", "message": "角色不正确"}
        updates: list[str] = []
        params: list[object] = []
        if display_name is not None:
            updates.append("display_name = ?")
            params.append(display_name.strip())
        if phone is not None:
            normalized_phone = "".join(ch for ch in phone.strip() if ch.isdigit())
            if normalized_phone and (len(normalized_phone) != 11 or not normalized_phone.startswith("1")):
                return {"error": "invalid_phone", "message": "请输入有效的11位手机号"}
            updates.append("phone = ?")
            params.append(normalized_phone or None)
        if role is not None:
            updates.append("role = ?")
            params.append(role)
        if plan is not None:
            updates.append("plan = ?")
            params.append(plan.strip() or "trial")
        if days is not None:
            expires_at = (datetime.now() + timedelta(days=max(int(days), 0))).isoformat(timespec="seconds") if int(days) > 0 else None
            updates.append("expires_at = ?")
            params.append(expires_at)
        if is_active is not None:
            updates.append("is_active = ?")
            params.append(1 if is_active else 0)
        if password:
            if len(password) < 6:
                return {"error": "weak_password", "message": "密码至少需要6位"}
            salt = secrets.token_hex(16)
            updates.extend(["salt = ?", "password_hash = ?"])
            params.extend([salt, self.hash_password(password, salt)])
        if not updates:
            with self.connect() as conn:
                row = conn.execute("select * from users where id = ?", (user_id,)).fetchone()
                return {"ok": bool(row), "user": self.public_user(row) if row else None}
        params.append(user_id)
        with self.connect() as conn:
            try:
                conn.execute(f"update users set {', '.join(updates)} where id = ?", params)
            except sqlite3.IntegrityError:
                return {"error": "user_exists", "message": "账号或手机号已存在"}
            row = conn.execute("select * from users where id = ?", (user_id,)).fetchone()
            if not row:
                return {"error": "not_found", "message": "会员不存在"}
            return {"ok": True, "user": self.public_user(row)}

    @staticmethod
    def hash_password(password: str, salt: str) -> str:
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000)
        return digest.hex()

    def verify_password(self, password: str, salt: str, expected_hash: str) -> bool:
        return hmac.compare_digest(self.hash_password(password, salt), expected_hash)

    def login(self, username: str, password: str) -> dict | None:
        with self.connect() as conn:
            account = username.strip()
            user = conn.execute("select * from users where username = ? or phone = ?", (account, account)).fetchone()
            if not user or not int(user["is_active"]):
                return None
            if user["expires_at"] and datetime.fromisoformat(user["expires_at"]) < datetime.now():
                return None
            if not self.verify_password(password, user["salt"], user["password_hash"]):
                return None
            token = secrets.token_urlsafe(32)
            expires_at = datetime.now() + timedelta(days=7)
            conn.execute(
                "insert into sessions (token, user_id, expires_at, created_at) values (?, ?, ?, ?)",
                (token, user["id"], expires_at.isoformat(timespec="seconds"), datetime.now().isoformat(timespec="seconds")),
            )
            return {"token": token, "user": self.public_user(user), "expires_at": expires_at.isoformat(timespec="seconds")}

    def logout(self, token: str) -> None:
        if not token:
            return
        with self.connect() as conn:
            conn.execute("delete from sessions where token = ?", (token,))

    def user_from_token(self, token: str) -> dict | None:
        if not token:
            return None
        with self.connect() as conn:
            row = conn.execute(
                """
                select u.* from sessions s
                join users u on u.id = s.user_id
                where s.token = ? and s.expires_at > ?
                """,
                (token, datetime.now().isoformat(timespec="seconds")),
            ).fetchone()
            if not row or not int(row["is_active"]):
                return None
            if row["expires_at"] and datetime.fromisoformat(row["expires_at"]) < datetime.now():
                return None
            return self.public_user(row)

    @staticmethod
    def public_user(row: sqlite3.Row) -> dict:
        plan = row["plan"]
        expires_at = row["expires_at"]
        return {
            "id": row["id"],
            "username": row["username"],
            "phone": row["phone"] if "phone" in row.keys() else "",
            "display_name": row["display_name"],
            "role": row["role"],
            "plan": plan,
            "expires_at": expires_at,
            "is_active": bool(row["is_active"]) if "is_active" in row.keys() else True,
            "membership": membership_summary(plan, expires_at),
        }
