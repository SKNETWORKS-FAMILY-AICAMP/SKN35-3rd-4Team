"""사용자 · 대화 기록 저장 (팀 ERD 2026-10-14, TiDB · 없으면 SQLite).

테이블 (팀 ERD 그대로)
    users         uuid(PK) · user_id(UNIQUE, 로그인 아이디) · created_at
    chat_history  uuid(PK) · user_id(FK → users.user_id) · session_id(대화방 단위) · question · answer · created_at
    관계: 사용자 1명 → 세션 여러 개 → 세션마다 질문 · 답변 여러 행. 인덱스 (session_id, created_at)

접속 정보 우선순위
    1. 환경 변수 MIGRATION_DB_URL (자동 점검용)
    2. .env 의 TIDB_HOST · TIDB_USER · TIDB_PASSWORD (+ TIDB_PORT=4000, TIDB_DATABASE=langchain_db) → TiDB (TLS)
    3. .streamlit/secrets.toml 의 [tidb] (host, port, user, password, database) → TiDB (Streamlit Cloud 용)
    4. 아무것도 없으면 data/local_chat_history.db (SQLite, 내 컴퓨터에서만)
TiDB 에 테이블이 이미 있으면 그대로 쓰고, 없으면 같은 구조로 만든다.
"""

import os
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from sqlalchemy import (Column, DateTime, ForeignKey, Index, MetaData, String, Table, Text, create_engine, func,
                        insert, select)
from sqlalchemy.exc import IntegrityError

ROOT = Path(__file__).resolve().parents[2]
meta = MetaData()

users = Table(
    "users", meta,
    Column("uuid", String(36), primary_key=True),
    Column("user_id", String(100), nullable=False, unique=True),
    Column("created_at", DateTime, nullable=False),
)
chat_history = Table(
    "chat_history", meta,
    Column("uuid", String(36), primary_key=True),
    Column("user_id", String(100), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False),
    Column("session_id", String(100), nullable=False),
    Column("question", Text, nullable=False),
    Column("answer", Text),
    Column("created_at", DateTime, nullable=False),
    Index("idx_chat_session", "session_id", "created_at"),
)


class UserIdTaken(Exception):
    """이미 있는 user_id 로 가입하려 할 때."""


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _new_uuid() -> str:
    return str(uuid.uuid4())


def _tidb_config() -> dict | None:
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass
    try:                                     # Secrets 에 .env 와 같은 이름(TIDB_HOST 등)으로 적은 경우
        import streamlit as st
        for k in ("TIDB_HOST", "TIDB_PORT", "TIDB_USER", "TIDB_PASSWORD", "TIDB_DATABASE"):
            if not os.environ.get(k) and k in st.secrets:
                os.environ[k] = str(st.secrets[k])
    except Exception:
        pass
    if os.environ.get("TIDB_HOST"):
        return {"host": os.environ["TIDB_HOST"], "port": os.environ.get("TIDB_PORT", 4000),
                "user": os.environ.get("TIDB_USER", ""), "password": os.environ.get("TIDB_PASSWORD", ""),
                "database": os.environ.get("TIDB_DATABASE", "langchain_db")}
    try:
        import streamlit as st
        cfg = st.secrets.get("tidb")
    except Exception:
        cfg = None
    return dict(cfg) if cfg else None


_tidb_error: str | None = None     # TiDB 접속 정보는 있는데 연결에 실패한 이유


def backend_name() -> str:
    if os.environ.get("MIGRATION_DB_URL"):
        return "test"
    engine()
    if _tidb_error:
        return f"SQLite(로컬) · TiDB 연결 실패: {_tidb_error}"
    return "TiDB" if _tidb_config() else "SQLite(로컬)"


def _sqlite():
    path = ROOT / "data" / "local_chat_history.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    eng = create_engine(f"sqlite:///{path}")
    meta.create_all(eng)
    return eng


@lru_cache(maxsize=1)
def engine():
    global _tidb_error
    if os.environ.get("MIGRATION_DB_URL"):
        eng = create_engine(os.environ["MIGRATION_DB_URL"])
        meta.create_all(eng)
        return eng
    cfg = _tidb_config()
    if not cfg:
        return _sqlite()
    if not all(str(cfg.get(k, "")).isascii() and cfg.get(k) for k in ("host", "user", "password")):
        _tidb_error = ".env 값이 아직 예시 그대로"
        return _sqlite()
    import certifi
    url = (f"mysql+pymysql://{quote_plus(str(cfg['user']))}:{quote_plus(str(cfg['password']))}"
           f"@{cfg['host']}:{cfg.get('port', 4000)}/{cfg.get('database', 'langchain_db')}?charset=utf8mb4")
    try:
        eng = create_engine(url, connect_args={"ssl": {"ca": certifi.where()}, "connect_timeout": 10},
                            pool_pre_ping=True, pool_recycle=300)
        meta.create_all(eng)          # 이미 있는 테이블은 건드리지 않음
        return eng
    except Exception as e:            # 값이 비었거나 틀리면 화면은 로컬 저장으로 계속 동작
        _tidb_error = type(e).__name__
        return _sqlite()


# ---------------------------------------------------------------- 사용자
def find_user(user_id: str) -> dict | None:
    with engine().connect() as c:
        row = c.execute(select(users).where(users.c.user_id == user_id)).mappings().first()
    return dict(row) if row else None


def user_id_taken(user_id: str) -> bool:
    """가입 전 중복 검사."""
    return find_user(user_id) is not None


def create_user(user_id: str) -> dict:
    """새 user_id 등록. 중복이면 UserIdTaken (미리 검사하고, 동시에 가입해도 UNIQUE 로 한 번 더 막음)."""
    if user_id_taken(user_id):
        raise UserIdTaken(user_id)
    row = {"uuid": _new_uuid(), "user_id": user_id, "created_at": _now()}
    try:
        with engine().begin() as c:
            c.execute(insert(users).values(**row))
    except IntegrityError:
        raise UserIdTaken(user_id) from None
    return row


# ---------------------------------------------------------------- 대화 (세션 = session_id 하나)
def new_session_id() -> str:
    return _new_uuid()


def add_turn(user_id: str, session_id: str, question: str, answer: str | None) -> None:
    """질문 하나와 그 답을 한 행으로 저장."""
    with engine().begin() as c:
        c.execute(insert(chat_history).values(uuid=_new_uuid(), user_id=user_id, session_id=session_id,
                                              question=question, answer=answer, created_at=_now()))


def list_sessions(user_id: str, limit: int = 50) -> list[dict]:
    """내 세션 목록 (최근 대화 순). 제목은 그 세션의 첫 질문."""
    h = chat_history
    with engine().connect() as c:
        rows = c.execute(select(h.c.session_id, func.min(h.c.created_at).label("started_at"),
                                func.max(h.c.created_at).label("last_at"), func.count().label("turns"))
                         .where(h.c.user_id == user_id).group_by(h.c.session_id)
                         .order_by(func.max(h.c.created_at).desc()).limit(limit)).mappings().all()
        out = []
        for r in rows:
            first = c.execute(select(h.c.question).where(h.c.session_id == r["session_id"])
                              .order_by(h.c.created_at).limit(1)).scalar() or ""
            out.append({**dict(r), "title": first.strip().splitlines()[0][:30] if first.strip() else "새 대화"})
    return out


def get_history(session_id: str, user_id: str) -> list[dict]:
    """내 세션의 질문 · 답변 (시간순). 다른 사용자의 세션이면 빈 목록."""
    h = chat_history
    with engine().connect() as c:
        rows = c.execute(select(h).where(h.c.session_id == session_id, h.c.user_id == user_id)
                         .order_by(h.c.created_at)).mappings().all()
    return [dict(r) for r in rows]


def session_info(session_id: str, user_id: str) -> dict | None:
    rows = get_history(session_id, user_id)
    return {"session_id": session_id, "started_at": rows[0]["created_at"], "turns": len(rows)} if rows else None
