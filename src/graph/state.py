from typing import Annotated, Literal, NotRequired, TypedDict
from langgraph.graph import MessagesState
from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

def merge_ids(left: list[str] | None, right: list[str] | None) -> list[str]:
    """재시도마다 verifier가 돌려주는 exclude_ids를 덮어쓰지 않고 누적한다(중복 제거)."""
    return sorted(set(left or []) | set(right or []))

class MigrationState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    classification: str
    question: str
    old_code: NotRequired[str]      # 사용자가 질문한 코드
    analysis: NotRequired[dict | str]      # 분석 결과 (analyzer는 dict로 넣음)
    target_version: NotRequired[str] # 목표 langchain 대표 버전 (예: "0.2.17"). 질문에 버전 언급 없으면 최신. normalize_version()으로 맞춘 값
    new_code: NotRequired[str]
    evidence_id: NotRequired[str]
    changes: NotRequired[list[dict]] # Rewriter가 구조화 출력으로 생성한 근거 ID가 포함된 변경 목록 저장
    install_packages: NotRequired[list[str]] # 새 코드가 import하는 langchain 계열 pip 패키지 목록
    verify_result: NotRequired[dict] # Verifier 검사 결과 (passed, errors, warnings, summary). errors는 다음 시도의 피드백으로 쓰임
    attempt: NotRequired[int] # verifier를 거친 횟수 verifier가 1씩 올리고 MAX_ATTEMPTS에 닿으면 종료
    rewrite_notes: NotRequired[list[str]] # 사용자에게 전달할 안내 사항을 LLM이 작성하여 저장
    unresolved: NotRequired[list[dict]] # 제시된 근거만으로는 확신할 수 없을 때 -> 바꾸지 못하고 원문 그대로 둔 코드, 이유
    exclude_ids: NotRequired[Annotated[list[str], merge_ids]] # 재시도할 때 틀린 근거가 누적되도록 merge_ids reducer 추가
    evidences: NotRequired[list[dict]] # Retriever가 찾은 근거 목록 (이번 코드에 매칭된 대응표 항목 + 문서 청크, Evidence.to_dict() 형태)
    shown_evidence_ids: NotRequired[list[str]] # Rewriter 프롬프트에 실제로 삽입된 근거 id들만 기록하여 이후 Verifier가 근거 id 존재 여부를 대조 검증할때
    rewrite_failed: NotRequired[bool] # LLM 호출이 실패했을 때 통과로 처리되지 않도록 플래그 추가
