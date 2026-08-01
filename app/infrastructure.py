from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any


class RedisCache:
    """Redis-backed JSON cache with an in-process TTL fallback for desktop mode."""

    def __init__(self) -> None:
        self.url = os.getenv("REDIS_URL", "").strip()
        self.client = None
        self.error = ""
        self.memory: dict[str, tuple[float, Any]] = {}
        self.lock = threading.Lock()
        if self.url:
            try:
                import redis

                self.client = redis.Redis.from_url(self.url, decode_responses=True, socket_timeout=1.5)
                self.client.ping()
            except Exception as exc:
                self.client = None
                self.error = str(exc)

    @property
    def backend(self) -> str:
        return "redis" if self.client else "memory"

    def get_json(self, key: str) -> Any | None:
        if self.client:
            try:
                value = self.client.get(key)
                return json.loads(value) if value else None
            except Exception as exc:
                self.error = str(exc)
        with self.lock:
            cached = self.memory.get(key)
            if not cached or cached[0] <= time.time():
                self.memory.pop(key, None)
                return None
            return cached[1]

    def set_json(self, key: str, value: Any, ttl: int = 5) -> None:
        if self.client:
            try:
                self.client.setex(key, ttl, json.dumps(value, ensure_ascii=False))
                return
            except Exception as exc:
                self.error = str(exc)
        with self.lock:
            self.memory[key] = (time.time() + ttl, value)

    def status(self) -> dict:
        return {"backend": self.backend, "configured": bool(self.url), "ok": bool(self.client) if self.url else True, "error": self.error}


class Persistence:
    """PostgreSQL persistence with a zero-setup SQLite fallback for the desktop build."""

    def __init__(self, data_dir: Path) -> None:
        self.database_url = os.getenv("DATABASE_URL", "").strip()
        self.sqlite_path = data_dir / "application.sqlite"
        self.backend = "sqlite"
        self.error = ""
        self._psycopg = None
        if self.database_url.startswith(("postgres://", "postgresql://")):
            try:
                import psycopg

                self._psycopg = psycopg
                with psycopg.connect(self.database_url, connect_timeout=3) as conn:
                    conn.execute("select 1")
                self.backend = "postgresql"
            except Exception as exc:
                self.error = str(exc)
        self.init_schema()

    @contextmanager
    def sqlite_connect(self):
        conn = sqlite3.connect(self.sqlite_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def postgres_connect(self):
        return self._psycopg.connect(self.database_url, connect_timeout=5)

    def init_schema(self) -> None:
        if self.backend == "postgresql":
            with self.postgres_connect() as conn:
                conn.execute("create table if not exists user_states (user_id bigint primary key, payload jsonb not null, updated_at timestamptz not null default now())")
                conn.execute("create table if not exists alert_rules (user_id bigint not null, code text not null, payload jsonb not null, updated_at timestamptz not null default now(), primary key (user_id, code))")
                conn.execute("create table if not exists ai_reports (id bigserial primary key, user_id bigint not null, code text not null, stock_name text not null, provider text not null, model text not null, system_prompt text not null, question text not null, result jsonb not null, created_at timestamptz not null default now())")
                conn.execute("create index if not exists ai_reports_user_code_idx on ai_reports(user_id, code, created_at desc)")
                conn.execute("create table if not exists screener_strategies (id bigserial primary key, user_id bigint not null, name text not null, description text not null default '', dsl jsonb not null, enabled boolean not null default true, created_at timestamptz not null default now(), updated_at timestamptz not null default now())")
                conn.execute("create index if not exists screener_strategies_user_idx on screener_strategies(user_id, updated_at desc)")
                conn.execute("create table if not exists stock_recommendations (id bigserial primary key, user_id bigint not null, code text not null, stock_name text not null, strategy_name text not null, entry_price double precision not null, reason text not null, risk_note text not null, source text not null, snapshot jsonb not null, metrics jsonb not null default '{}'::jsonb, created_at timestamptz not null default now())")
                conn.execute("create index if not exists stock_recommendations_user_idx on stock_recommendations(user_id, created_at desc)")
                conn.execute("create table if not exists recommendation_prices (recommendation_id bigint not null references stock_recommendations(id) on delete cascade, user_id bigint not null, trade_date date not null, close_price double precision not null, primary key(recommendation_id, trade_date))")
                conn.execute("create table if not exists abnormal_events (id bigserial primary key, user_id bigint not null, items jsonb not null, meta jsonb not null default '{}'::jsonb, created_at timestamptz not null default now())")
                conn.execute("create index if not exists abnormal_events_user_idx on abnormal_events(user_id, created_at desc)")
                conn.execute("create table if not exists industry_chain_reports (id bigserial primary key, user_id bigint not null, topic text not null, payload jsonb not null, created_at timestamptz not null default now())")
                conn.execute("create index if not exists industry_chain_reports_user_idx on industry_chain_reports(user_id, created_at desc)")
            return
        with self.sqlite_connect() as conn:
            conn.execute("create table if not exists user_states (user_id integer primary key, payload text not null, updated_at text not null)")
            conn.execute("create table if not exists alert_rules (user_id integer not null, code text not null, payload text not null, updated_at text not null, primary key (user_id, code))")
            conn.execute("create table if not exists ai_reports (id integer primary key autoincrement, user_id integer not null, code text not null, stock_name text not null, provider text not null, model text not null, system_prompt text not null, question text not null, result text not null, created_at text not null)")
            conn.execute("create index if not exists ai_reports_user_code_idx on ai_reports(user_id, code, created_at desc)")
            conn.execute("create table if not exists screener_strategies (id integer primary key autoincrement, user_id integer not null, name text not null, description text not null default '', dsl text not null, enabled integer not null default 1, created_at text not null, updated_at text not null)")
            conn.execute("create index if not exists screener_strategies_user_idx on screener_strategies(user_id, updated_at desc)")
            conn.execute("create table if not exists stock_recommendations (id integer primary key autoincrement, user_id integer not null, code text not null, stock_name text not null, strategy_name text not null, entry_price real not null, reason text not null, risk_note text not null, source text not null, snapshot text not null, metrics text not null, created_at text not null)")
            conn.execute("create index if not exists stock_recommendations_user_idx on stock_recommendations(user_id, created_at desc)")
            conn.execute("create table if not exists recommendation_prices (recommendation_id integer not null, user_id integer not null, trade_date text not null, close_price real not null, primary key(recommendation_id, trade_date), foreign key(recommendation_id) references stock_recommendations(id) on delete cascade)")
            conn.execute("create table if not exists abnormal_events (id integer primary key autoincrement, user_id integer not null, items text not null, meta text not null, created_at text not null)")
            conn.execute("create index if not exists abnormal_events_user_idx on abnormal_events(user_id, created_at desc)")
            conn.execute("create table if not exists industry_chain_reports (id integer primary key autoincrement, user_id integer not null, topic text not null, payload text not null, created_at text not null)")
            conn.execute("create index if not exists industry_chain_reports_user_idx on industry_chain_reports(user_id, created_at desc)")

    def get_user_state(self, user_id: int) -> dict | None:
        if self.backend == "postgresql":
            with self.postgres_connect() as conn:
                row = conn.execute("select payload from user_states where user_id=%s", (user_id,)).fetchone()
                return row[0] if row else None
        with self.sqlite_connect() as conn:
            row = conn.execute("select payload from user_states where user_id=?", (user_id,)).fetchone()
            return json.loads(row[0]) if row else None

    def save_user_state(self, user_id: int, state: dict) -> None:
        positions = state.get("positions", {})
        now = datetime.now().isoformat(timespec="seconds")
        if self.backend == "postgresql":
            from psycopg.types.json import Jsonb

            with self.postgres_connect() as conn:
                conn.execute("insert into user_states(user_id,payload,updated_at) values(%s,%s,now()) on conflict(user_id) do update set payload=excluded.payload,updated_at=now()", (user_id, Jsonb(state)))
                for code, rule in positions.items():
                    conn.execute("insert into alert_rules(user_id,code,payload,updated_at) values(%s,%s,%s,now()) on conflict(user_id,code) do update set payload=excluded.payload,updated_at=now()", (user_id, code, Jsonb(rule)))
            return
        payload = json.dumps(state, ensure_ascii=False)
        with self.sqlite_connect() as conn:
            conn.execute("insert into user_states(user_id,payload,updated_at) values(?,?,?) on conflict(user_id) do update set payload=excluded.payload,updated_at=excluded.updated_at", (user_id, payload, now))
            for code, rule in positions.items():
                conn.execute("insert into alert_rules(user_id,code,payload,updated_at) values(?,?,?,?) on conflict(user_id,code) do update set payload=excluded.payload,updated_at=excluded.updated_at", (user_id, code, json.dumps(rule, ensure_ascii=False), now))

    def save_ai_report(self, *, user_id: int, code: str, stock_name: str, provider: str, model: str, system_prompt: str, question: str, result: dict) -> int:
        if self.backend == "postgresql":
            from psycopg.types.json import Jsonb

            with self.postgres_connect() as conn:
                row = conn.execute("insert into ai_reports(user_id,code,stock_name,provider,model,system_prompt,question,result) values(%s,%s,%s,%s,%s,%s,%s,%s) returning id", (user_id, code, stock_name, provider, model, system_prompt, question, Jsonb(result))).fetchone()
                return int(row[0])
        with self.sqlite_connect() as conn:
            cursor = conn.execute("insert into ai_reports(user_id,code,stock_name,provider,model,system_prompt,question,result,created_at) values(?,?,?,?,?,?,?,?,?)", (user_id, code, stock_name, provider, model, system_prompt, question, json.dumps(result, ensure_ascii=False), datetime.now().isoformat(timespec="seconds")))
            return int(cursor.lastrowid)

    def list_ai_reports(self, user_id: int, code: str = "", limit: int = 30) -> list[dict]:
        if self.backend == "postgresql":
            sql = "select id,code,stock_name,provider,model,question,result,created_at from ai_reports where user_id=%s"
            args: list[Any] = [user_id]
            if code:
                sql += " and code=%s"
                args.append(code)
            sql += " order by created_at desc limit %s"
            args.append(limit)
            with self.postgres_connect() as conn:
                rows = conn.execute(sql, tuple(args)).fetchall()
            return [{"id": r[0], "code": r[1], "stock_name": r[2], "provider": r[3], "model": r[4], "question": r[5], "result": r[6], "created_at": r[7].isoformat()} for r in rows]
        sql = "select id,code,stock_name,provider,model,question,result,created_at from ai_reports where user_id=?"
        args = [user_id]
        if code:
            sql += " and code=?"
            args.append(code)
        sql += " order by created_at desc limit ?"
        args.append(limit)
        with self.sqlite_connect() as conn:
            rows = conn.execute(sql, tuple(args)).fetchall()
        return [{"id": r[0], "code": r[1], "stock_name": r[2], "provider": r[3], "model": r[4], "question": r[5], "result": json.loads(r[6]), "created_at": r[7]} for r in rows]

    def save_screener_strategy(self, user_id: int, payload: dict) -> int:
        now = datetime.now().isoformat(timespec="seconds")
        if self.backend == "postgresql":
            from psycopg.types.json import Jsonb
            with self.postgres_connect() as conn:
                row = conn.execute("insert into screener_strategies(user_id,name,description,dsl,enabled) values(%s,%s,%s,%s,%s) returning id", (user_id, payload["name"], payload.get("description", ""), Jsonb(payload["dsl"]), bool(payload.get("enabled", True)))).fetchone()
                return int(row[0])
        with self.sqlite_connect() as conn:
            cursor = conn.execute("insert into screener_strategies(user_id,name,description,dsl,enabled,created_at,updated_at) values(?,?,?,?,?,?,?)", (user_id, payload["name"], payload.get("description", ""), json.dumps(payload["dsl"], ensure_ascii=False), int(bool(payload.get("enabled", True))), now, now))
            return int(cursor.lastrowid)

    def list_screener_strategies(self, user_id: int) -> list[dict]:
        if self.backend == "postgresql":
            with self.postgres_connect() as conn:
                rows = conn.execute("select id,name,description,dsl,enabled,created_at,updated_at from screener_strategies where user_id=%s order by updated_at desc", (user_id,)).fetchall()
            return [{"id": row[0], "name": row[1], "description": row[2], "dsl": row[3], "enabled": row[4], "created_at": row[5].isoformat(), "updated_at": row[6].isoformat()} for row in rows]
        with self.sqlite_connect() as conn:
            rows = conn.execute("select id,name,description,dsl,enabled,created_at,updated_at from screener_strategies where user_id=? order by updated_at desc", (user_id,)).fetchall()
        return [{"id": row[0], "name": row[1], "description": row[2], "dsl": json.loads(row[3]), "enabled": bool(row[4]), "created_at": row[5], "updated_at": row[6]} for row in rows]

    def delete_screener_strategy(self, user_id: int, strategy_id: int) -> bool:
        sql = "delete from screener_strategies where user_id=%s and id=%s" if self.backend == "postgresql" else "delete from screener_strategies where user_id=? and id=?"
        connection = self.postgres_connect if self.backend == "postgresql" else self.sqlite_connect
        with connection() as conn:
            cursor = conn.execute(sql, (user_id, strategy_id))
            return cursor.rowcount > 0

    def save_stock_recommendation(self, user_id: int, payload: dict) -> int:
        metrics = payload.get("metrics") or {}
        if self.backend == "postgresql":
            from psycopg.types.json import Jsonb
            with self.postgres_connect() as conn:
                row = conn.execute("insert into stock_recommendations(user_id,code,stock_name,strategy_name,entry_price,reason,risk_note,source,snapshot,metrics) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) returning id", (user_id, payload["code"], payload["stock_name"], payload["strategy_name"], payload["entry_price"], payload.get("reason", ""), payload.get("risk_note", ""), payload.get("source", ""), Jsonb(payload.get("snapshot") or {}), Jsonb(metrics))).fetchone()
                return int(row[0])
        with self.sqlite_connect() as conn:
            cursor = conn.execute("insert into stock_recommendations(user_id,code,stock_name,strategy_name,entry_price,reason,risk_note,source,snapshot,metrics,created_at) values(?,?,?,?,?,?,?,?,?,?,?)", (user_id, payload["code"], payload["stock_name"], payload["strategy_name"], float(payload["entry_price"]), payload.get("reason", ""), payload.get("risk_note", ""), payload.get("source", ""), json.dumps(payload.get("snapshot") or {}, ensure_ascii=False), json.dumps(metrics, ensure_ascii=False), datetime.now().isoformat(timespec="seconds")))
            return int(cursor.lastrowid)

    def list_stock_recommendations(self, user_id: int, limit: int = 100) -> list[dict]:
        placeholder = "%s" if self.backend == "postgresql" else "?"
        sql = f"select id,code,stock_name,strategy_name,entry_price,reason,risk_note,source,snapshot,metrics,created_at from stock_recommendations where user_id={placeholder} order by created_at desc limit {placeholder}"
        connection = self.postgres_connect if self.backend == "postgresql" else self.sqlite_connect
        with connection() as conn:
            rows = conn.execute(sql, (user_id, limit)).fetchall()
        result = []
        for row in rows:
            snapshot = row[8] if self.backend == "postgresql" else json.loads(row[8])
            metrics = row[9] if self.backend == "postgresql" else json.loads(row[9])
            created_at = row[10].isoformat() if self.backend == "postgresql" else row[10]
            result.append({"id": row[0], "code": row[1], "stock_name": row[2], "strategy_name": row[3], "entry_price": row[4], "reason": row[5], "risk_note": row[6], "source": row[7], "snapshot": snapshot, "metrics": metrics, "created_at": created_at})
        return result

    def record_recommendation_prices(self, user_id: int, price_map: dict[str, float], trade_date: str) -> None:
        recommendations = self.list_stock_recommendations(user_id, 500)
        rows = [(item["id"], user_id, trade_date, float(price_map[item["code"]])) for item in recommendations if item["code"] in price_map and float(price_map[item["code"]]) > 0]
        if not rows:
            return
        if self.backend == "postgresql":
            with self.postgres_connect() as conn:
                conn.executemany("insert into recommendation_prices(recommendation_id,user_id,trade_date,close_price) values(%s,%s,%s,%s) on conflict(recommendation_id,trade_date) do update set close_price=excluded.close_price", rows)
            return
        with self.sqlite_connect() as conn:
            conn.executemany("insert into recommendation_prices(recommendation_id,user_id,trade_date,close_price) values(?,?,?,?) on conflict(recommendation_id,trade_date) do update set close_price=excluded.close_price", rows)

    def recommendation_price_history(self, user_id: int, recommendation_ids: list[int]) -> dict[int, list[float]]:
        result = {int(item): [] for item in recommendation_ids}
        if not recommendation_ids:
            return result
        marker = "%s" if self.backend == "postgresql" else "?"
        markers = ",".join(marker for _ in recommendation_ids)
        sql = f"select recommendation_id,close_price from recommendation_prices where user_id={marker} and recommendation_id in ({markers}) order by trade_date asc"
        connection = self.postgres_connect if self.backend == "postgresql" else self.sqlite_connect
        with connection() as conn:
            rows = conn.execute(sql, tuple([user_id, *recommendation_ids])).fetchall()
        for recommendation_id, price in rows:
            result.setdefault(int(recommendation_id), []).append(float(price))
        return result

    def save_abnormal_events(self, user_id: int, items: list[dict], meta: dict | None = None) -> int:
        meta = meta or {}
        if self.backend == "postgresql":
            from psycopg.types.json import Jsonb

            with self.postgres_connect() as conn:
                row = conn.execute("insert into abnormal_events(user_id,items,meta) values(%s,%s,%s) returning id", (user_id, Jsonb(items), Jsonb(meta))).fetchone()
                return int(row[0])
        with self.sqlite_connect() as conn:
            cursor = conn.execute(
                "insert into abnormal_events(user_id,items,meta,created_at) values(?,?,?,?)",
                (user_id, json.dumps(items, ensure_ascii=False), json.dumps(meta, ensure_ascii=False), datetime.now().isoformat(timespec="seconds")),
            )
            return int(cursor.lastrowid)

    def list_abnormal_events(self, user_id: int, limit: int = 100) -> dict:
        marker = "%s" if self.backend == "postgresql" else "?"
        sql = f"select id,items,meta,created_at from abnormal_events where user_id={marker} order by created_at desc limit {marker}"
        connection = self.postgres_connect if self.backend == "postgresql" else self.sqlite_connect
        with connection() as conn:
            rows = conn.execute(sql, (user_id, limit)).fetchall()
        snapshots = []
        items: list[dict] = []
        for row in rows:
            snapshot_items = row[1] if self.backend == "postgresql" else json.loads(row[1])
            meta = row[2] if self.backend == "postgresql" else json.loads(row[2])
            created_at = row[3].isoformat() if self.backend == "postgresql" else row[3]
            snapshots.append({"id": row[0], "items": snapshot_items, "meta": meta, "created_at": created_at})
            items.extend(snapshot_items)
        return {"items": items[:limit], "snapshots": snapshots, "total": len(items)}

    def save_industry_chain_report(self, user_id: int, report: dict) -> int:
        topic = str(report.get("topic") or report.get("title") or "产业链分析")
        if self.backend == "postgresql":
            from psycopg.types.json import Jsonb

            with self.postgres_connect() as conn:
                row = conn.execute("insert into industry_chain_reports(user_id,topic,payload) values(%s,%s,%s) returning id", (user_id, topic, Jsonb(report))).fetchone()
                return int(row[0])
        with self.sqlite_connect() as conn:
            cursor = conn.execute(
                "insert into industry_chain_reports(user_id,topic,payload,created_at) values(?,?,?,?)",
                (user_id, topic, json.dumps(report, ensure_ascii=False), datetime.now().isoformat(timespec="seconds")),
            )
            return int(cursor.lastrowid)

    def list_industry_chain_reports(self, user_id: int, limit: int = 30) -> list[dict]:
        marker = "%s" if self.backend == "postgresql" else "?"
        sql = f"select id,topic,payload,created_at from industry_chain_reports where user_id={marker} order by created_at desc limit {marker}"
        connection = self.postgres_connect if self.backend == "postgresql" else self.sqlite_connect
        with connection() as conn:
            rows = conn.execute(sql, (user_id, limit)).fetchall()
        result = []
        for row in rows:
            payload = row[2] if self.backend == "postgresql" else json.loads(row[2])
            created_at = row[3].isoformat() if self.backend == "postgresql" else row[3]
            result.append({"id": row[0], "topic": row[1], "payload": payload, "created_at": created_at})
        return result

    def status(self) -> dict:
        return {"backend": self.backend, "postgresql_configured": bool(self.database_url), "ok": not bool(self.error) or self.backend == "sqlite", "fallback_reason": self.error}
