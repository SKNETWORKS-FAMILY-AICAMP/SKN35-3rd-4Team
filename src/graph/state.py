from typing import Annotated, Literal
from langgraph.graph import MessagesState
from pydantic import BaseModel, Field

class MigrateState(BaseModel):
    old: str
    new: str
    evidence_id: str
    kind: Literal["native", "classic_fallback"]