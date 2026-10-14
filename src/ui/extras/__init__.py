"""선택 기능 (4번 영역이 아님). 팀 저장소에 합칠 때 이 폴더를 통째로 빼도 화면은 그대로 동작한다.

    followups.py       연상 질문(이어서 물어보기) · 코드 없는 질문 답변   (LLM 대화 기능)
    version_detect.py  지금 코드가 어느 버전 시기인지 자동 감지           (코드 분석 → analyzer 쪽 일)
    version_map.py     버전 ↔ 버전 import 대응 (되돌리기 포함)            (변환 로직 → retriever / rewriter 쪽 일)

화면 쪽에서는 src/ui/optional.py 의 load() 로만 불러서, 폴더가 없으면 None 을 받고 그 기능만 빠진다.
자세한 정리: docs/머지_가이드.md
"""
