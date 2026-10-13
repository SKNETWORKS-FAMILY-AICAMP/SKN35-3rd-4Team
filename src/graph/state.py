from typing import Annotated, Literal, NotRequired, TypedDict
from langgraph.graph import MessagesState
from pydantic import BaseModel, Field

class MigrationState(TypedDict):
    question: str
    old_code: NotRequired[str]      # 사용자가 질문한 코드
    analysis: NotRequired[str]      # 분석 결과
    new_code: NotRequired[str]
    evidence_id: NotRequired[str]
    # kind: Literal["native", "classic_fallback"]