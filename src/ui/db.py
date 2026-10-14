"""사용자 · 대화 기록 저장 (TiDB, 없으면 SQLite).

접속 정보 우선순위
    1. 환경 변수 MIGRATION_DB_URL (시험용)
    2. .streamlit/secrets.toml 의 [tidb] (host, port, user, password, database) → TiDB (MySQL 호환, TLS)
    3. 둘 다 없으면 data/local_chat.db (SQLite, 내 컴퓨터에서만)

테이블
    users          user_id(PK) · username(UNIQUE, 중복 금지) · created_at
    conversations  conv_id(PK) · user_id(FK) · title · source_version · target_version · created_at · updated_at
    messages       msg_id(PK) · conv_id(FK) · role(user/assistant) · content · result_json · created_at
"""

import json
import os
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from sqlalchemy import (Column, DateTime, ForeignKey, Integer, MetaData, String, Table, Text, create_engine,
                        func, insert, select, update)
from sqlalchemy.exc import IntegrityError

ROOT = Path(__file__).resolve().parents[2]
meta = MetaData()

users = Table(
    "users", meta,
    Column("user_id", Integer, primary_key=True, autoincrement=True),
    Column("username", String(50), nullable=False, unique=True),
    Column("created_at", DateTime, nullable=False),
)
conversations = Table(
    "conversations", meta,
    Column("conv_id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", Integer, ForeignKey("users.user_id"), nullable=False, index=True),
    Column("title", String(100), nullable=False),
    Column("source_version", String(20)),
    Column("target_version", String(20)),
    Column("created_at", DateTime, nullable=False),
    Column("updated_at", DateTime, nullable=False),
)
messages = Table(
    "messages", meta,
    Column("msg_id", Integer, primary_key=True, autoincrement=True),
    Column("conv_id", Integer, ForeignKey("conversations.conv_id"), nullable=False, index=True),
    Column("role", String(10), nullable=False),
    Column("content", Text, nullable=False),
    Column("result_json", Text),            # 결과 패널에 다시 그릴 결과 (assistant 메시지만)
    Column("created_at", DateTime, nullable=False),
)


class UsernameTaken(Exception):
    """이미 있는 username 으로 가입하려 할 때."""


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _tidb_url() -> tuple[str, dict] | None:
    try:
        import streamlit as st
        cfg = st.secrets.get("tidb")
    except Exception:
        cfg = None
    if not cfg:
        return None
    import certifi
    url = (f"mysql+pymysql://{quote_plus(cfg['user'])}:{quote_plus(cfg['password'])}"
           f"@{cfg['host']}:{cfg.get('port', 4000)}/{cfg.get('database', 'migration_chat')}?charset=utf8mb4")
    return url, {"ssl": {"ca": certifi.where()}}


def backend_name() -> str:
    if os.environ.get("MIGRATION_DB_URL"):
        return "test"
    return "TiDB" if _tidb_url() else "SQLite(로컬)"


@lru_cache(maxsize=1)
def engine():
    if os.environ.get("MIGRATION_DB_URL"):
        eng = create_engine(os.environ["MIGRATION_DB_URL"])
    elif tidb := _tidb_url():
        url, connect_args = tidb
        eng = create_engine(url, connect_args=connect_args, pool_pre_ping=True, pool_recycle=300)
    else:
        path = ROOT / "data" / "local_chat.db"
        path.parent.mkdir(parents=True, exist_ok=True)
        eng = create_engine(f"sqlite:///{path}")
    meta.create_all(eng)
    return eng


# ---------------------------------------------------------------- 사용자
def find_user(username: str) -> dict | None:
    with engine().connect() as c:
        row = c.execute(select(users).where(users.c.username == username)).mappings().first()
    return dict(row) if row else None


def create_user(username: str) -> dict:
    """새 username 등록. 이미 있으면 UsernameTaken."""
    try:
        with engine().begin() as c:
            uid = c.execute(insert(users).values(username=username, created_at=_now())).inserted_primary_key[0]
    except IntegrityError:
        raise UsernameTaken(username) from None
    return {"user_id": uid, "username": username}


# ---------------------------------------------------------------- 대화
def list_conversations(user_id: int, limit: int = 50) -> list[dict]:
    with engine().connect() as c:
        rows = c.execute(select(conversations).where(conversations.c.user_id == user_id)
                         .order_by(conversations.c.updated_at.desc()).limit(limit)).mappings().all()
    return [dict(r) for r in rows]


def create_conversation(user_id: int, title: str, source_version: str | None, target_version: str) -> int:
    with engine().begin() as c:
        return c.execute(insert(conversations).values(
            user_id=user_id, title=title[:100], source_version=source_version or "auto",
            target_version=target_version, created_at=_now(), updated_at=_now())).inserted_primary_key[0]


def get_conversation(conv_id: int, user_id: int) -> dict | None:
    """내 대화(세션) 하나의 정보. 다른 사용자 것이면 None."""
    with engine().connect() as c:
        row = c.execute(select(conversations).where(conversations.c.conv_id == conv_id,
                                                    conversations.c.user_id == user_id)).mappings().first()
    return dict(row) if row else None


def get_messages(conv_id: int, user_id: int) -> list[dict]:
    """내 대화의 메시지만 돌려준다 (다른 사용자의 conv_id 를 넣으면 빈 목록)."""
    with engine().connect() as c:
        owner = c.execute(select(conversations.c.user_id).where(conversations.c.conv_id == conv_id)).scalar()
        if owner != user_id:
            return []
        rows = c.execute(select(messages).where(messages.c.conv_id == conv_id)
                         .order_by(messages.c.msg_id)).mappings().all()
    out = []
    for r in rows:
        m = dict(r)
        m["result"] = json.loads(m.pop("result_json")) if m.get("result_json") else None
        out.append(m)
    return out


def add_message(conv_id: int, role: str, content: str, result: dict | None = None) -> None:
    with engine().begin() as c:
        c.execute(insert(messages).values(conv_id=conv_id, role=role, content=content,
                                          result_json=json.dumps(result, ensure_ascii=False) if result else None,
                                          created_at=_now()))
        c.execute(update(conversations).where(conversations.c.conv_id == conv_id).values(updated_at=_now()))


def count_messages(conv_id: int) -> int:
    with engine().connect() as c:
        return c.execute(select(func.count()).select_from(messages).where(messages.c.conv_id == conv_id)).scalar()
