import argparse
import hashlib
import json
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ..import_map import LATEST_VERSION, VERSION_SETS
from ..import_map.build_import_map import version_key
from ..import_map.version_resolve import Resolution, normalize_version, resolve
from . import (
    CANDIDATES, CHUNKS_PATH, DEFAULT_K, DOC_REF_BOOST, DOC_SOURCES, ERA_WEIGHT, ERA_WEIGHT_0X, FUZZY_MAP_K,
    IMPORT_LINK_BOOST, MAX_PER_PAGE, RRF_K,
)
from .bm25 import BM25
from .import_lookup import MapHit, lookup, lookup_methods, parse_import_paths


@dataclass
class Evidence:
    evidence_id: str
    source: str                 # import_map | method_map | latest_docs | migration_guide
    match: str                  # exact | exact_method | fuzzy_map | hybrid
    score: float
    text: str
    era: str | None = None
    url: str | None = None
    title: str | None = None
    section: str | None = None
    old: str | None = None      # 대응표 근거: 사용자 코드의 경로 / 메서드 근거: Class.method
    new: str | None = None      # 대응표 근거: 1.x 경로 (unresolved 면 None) / 메서드 근거: 대체 메서드
    kind: str | None = None     # native | classic_fallback | unresolved / 메서드: removed | deprecated | exists
    import_status: str | None = None
    alternative: str | None = None
    signals: list[str] = field(default_factory=list)   # 재정렬 근거 (디버깅용)

    def to_dict(self) -> dict:
        return asdict(self)


def open_store():
    from langchain_chroma import Chroma
    from langchain_openai import OpenAIEmbeddings

    from ..embedding import COLLECTION_NAME, EMBEDDING_DIMENSIONS, EMBEDDING_MODEL, cloud_client

    client = cloud_client()
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=OpenAIEmbeddings(model=EMBEDDING_MODEL, dimensions=EMBEDDING_DIMENSIONS),
        client=client,
        create_collection_if_not_exists=False,
    )


def rrf(rankings: list[list[str]]) -> dict[str, float]:
    scores: dict[str, float] = defaultdict(float)
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking):
            scores[chunk_id] += 1 / (RRF_K + rank + 1)
    return scores


def loose_key(path: str) -> tuple[str, str]:
    """langchain_openai.chat_models.base.ChatOpenAI 와 langchain_openai.ChatOpenAI 를 같게 본다."""
    return path.split(".")[0], path.rsplit(".", 1)[-1]


class RetrievalEngine:
    def __init__(self, store=None):
        with CHUNKS_PATH.open(encoding="utf-8") as f:
            chunks = [json.loads(line) for line in f]
        self.chunks = {c["chunk_id"]: c for c in chunks}
        self.doc_ids = [c["chunk_id"] for c in chunks if c["source"] in DOC_SOURCES]
        self.map_ids = [c["chunk_id"] for c in chunks if c["source"] == "import_map"]
        self.doc_bm25 = BM25([self.chunks[i]["text"] for i in self.doc_ids])
        self.page_doc_idx: dict[str, set[int]] = defaultdict(set)  # 문서 페이지 → doc_ids 인덱스
        for idx, chunk_id in enumerate(self.doc_ids):
            self.page_doc_idx[self.chunks[chunk_id]["path"]].add(idx)
        self.map_bm25 = BM25([self.chunks[i]["text"] for i in self.map_ids])
        # 청크가 실제로 import 하는 경로 (정답 import 를 쓰는 문서 가산용)
        self.chunk_import_keys = {
            i: {loose_key(p) for p in parse_import_paths("\n".join(self.chunks[i]["imports"]))}
            for i in self.doc_ids
        }
        self._store = store

    @property
    def store(self):
        if self._store is None:
            self._store = open_store()  # OpenAI 키가 필요해서 처음 쓸 때 연다
        return self._store

    # ------------------------------------------------------------ 후보 검색

    def _vector(self, query: str, sources: tuple[str, ...], n: int) -> list[str]:
        where = {"source": sources[0]} if len(sources) == 1 else {"source": {"$in": list(sources)}}
        docs = self.store.similarity_search(query, k=n, filter=where)
        return [d.id for d in docs if d.id in self.chunks]

    def _hybrid(self, query: str, sources: tuple[str, ...], n: int) -> dict[str, float]:
        if sources == ("import_map",):
            bm25, ids = self.map_bm25, self.map_ids
        else:
            bm25, ids = self.doc_bm25, self.doc_ids
        lexical = [ids[i] for i, _ in bm25.search(query, n)]
        return rrf([self._vector(query, sources, n), lexical])

    # ------------------------------------------------------------ 근거 변환

    def _map_evidence(self, hit: MapHit, match: str, score: float) -> Evidence:
        rec = hit.record
        chunk = self.chunks.get(rec["id"], {})
        return Evidence(
            evidence_id=rec["id"], source="import_map", match=match, score=score,
            text=chunk.get("text", ""), era="1.x", old=hit.query_path, new=hit.new, kind=rec["kind"],
            import_status=rec["import_status"], alternative=rec.get("alternative"),
            signals=["via_module"] if hit.via_module else [],
        )

    @staticmethod
    def _seen_in_1x(path: str) -> bool:
        """1.x 대표 버전 중 하나에라도 있던 경로 (1.x 안에서 사라진 것 → 유사 검색보다 '대응 없음'이 정확)."""
        return any(resolve(path, v).status == "keep" for v in VERSION_SETS if version_key(v)[0] >= 1)

    def _version_evidence(self, res: Resolution) -> Evidence:
        """목표 버전 판정 결과 → import_map 형식 근거 (rewriter·verifier가 같은 필드를 읽도록).
        같은 대응표 레코드를 여러 경로가 거칠 수 있어 id는 (목표 버전, 경로)로 따로 만든다."""
        evidence_id = "vres-" + hashlib.sha1(f"{res.target}|{res.path}".encode()).hexdigest()[:10]
        if res.status == "moved":
            kind = "classic_fallback" if res.new.startswith("langchain_classic.") else "native"
            text = f"Legacy import: {res.path}\nLangChain {res.target} import: {res.new}"
        else:
            kind = "unresolved"
            text = f"Legacy import: {res.path}\nLangChain {res.target} import: (no equivalent)"
        signals = [f"target:{res.target}", *(f"via:{i}" for i in res.evidence_ids)]
        if not res.verified:
            signals.append("unverified")
        if res.deprecated:
            signals.append("deprecated_in_target")
        return Evidence(
            evidence_id=evidence_id, source="import_map", match="exact", score=1.0, text=text, era=res.target,
            old=res.path, new=res.new if res.status == "moved" else None, kind=kind,
            alternative=res.alternative, signals=signals,
        )

    def _method_evidence(self, rec: dict) -> Evidence:
        chunk = self.chunks.get(rec["id"], {})
        return Evidence(
            evidence_id=rec["id"], source="method_map", match="exact_method", score=1.0,
            text=chunk.get("text", ""), era="1.x", old=f"{rec['class']}.{rec['method']}",
            new=rec.get("alternative"), kind=rec["status_1x"], alternative=rec.get("note"),
            signals=[rec["call"]],
        )

    def _doc_evidence(self, chunk_id: str, score: float, signals: list[str]) -> Evidence:
        c = self.chunks[chunk_id]
        return Evidence(
            evidence_id=chunk_id, source=c["source"], match="hybrid", score=round(score, 5),
            text=c["text"], era=c["era"], url=c.get("url"), title=c.get("title"),
            section=c.get("section"), signals=signals,
        )

    # ------------------------------------------------------------ 진입점

    def retrieve(
        self,
        query: str,
        old_path: str | None = None,
        k: int = DEFAULT_K,
        exclude_ids: set[str] | frozenset[str] = frozenset(),
        attempt: int = 0,
        target_version: str | None = None,
    ) -> list[Evidence]:
        width = attempt + 1
        paths = parse_import_paths(old_path) if old_path else parse_import_paths(query)
        target = normalize_version(target_version)
        latest = target == LATEST_VERSION

        # ① 대응표 정확매칭 (최신이 아니면 목표 버전 기준 판정, 그대로 둬도 되는 경로는 근거 없음)
        map_evidence: list[Evidence] = []
        unmatched = []
        for path in paths:
            if not latest:
                res = resolve(path, target)
                if res.status in ("moved", "not_available"):
                    ev = self._version_evidence(res)
                    if ev.evidence_id not in exclude_ids:
                        map_evidence.append(ev)
                continue
            hit = lookup(path)
            if hit is None:
                # 대응표에 없는 경로: 최신에 그대로 있으면 근거 불필요, 1.x 안에서 옮겨졌으면 판정 근거,
                # 판정도 못 하면 유사 검색으로
                res = resolve(path, target)
                if res.status == "moved" or (res.status == "not_available" and self._seen_in_1x(path)):
                    ev = self._version_evidence(res)
                    if ev.evidence_id not in exclude_ids:
                        map_evidence.append(ev)
                elif res.status != "keep":
                    unmatched.append(path)
            elif hit.record["id"] not in exclude_ids:
                map_evidence.append(self._map_evidence(hit, "exact", 1.0))

        # ② 메서드 호출 정확매칭 (chain.run(), llm.predict(), llm("...") 등)
        #    최신이 아니면 목표 버전에서 이미 deprecated된 메서드만 (그 전 버전엔 대체 메서드가 없을 수 있다)
        method_hits = [r for r in lookup_methods(query) if r["id"] not in exclude_ids
                        and (latest or (r.get("since") and version_key(r["since"]) <= version_key(target)))]
        method_evidence = [self._method_evidence(r) for r in method_hits]
        doc_refs = {p for r in method_hits for p in r.get("doc_refs", [])}

        # ③ 못 찾은 경로는 대응표 유사 검색 (같은 1.x 경로는 하나만)
        for path in unmatched:
            seen_new = set()
            scored = self._hybrid(path, ("import_map",), CANDIDATES * width)
            for chunk_id, score in sorted(scored.items(), key=lambda x: -x[1]):
                c = self.chunks[chunk_id]
                if chunk_id in exclude_ids or c["new"] in seen_new:
                    continue
                seen_new.add(c["new"])
                hit = lookup(c["old"])
                if hit:
                    ev = self._map_evidence(hit, "fuzzy_map", round(score, 5))
                    ev.old = path
                    ev.signals.append(f"similar_to:{c['old']}")
                    map_evidence.append(ev)
                if len(seen_new) >= FUZZY_MAP_K:
                    break

        # ④ 문서 하이브리드 검색 (정확매칭된 1.x 경로·대안 텍스트로 질의 확장)
        exact = [e for e in map_evidence if e.match == "exact"]
        expansion = [e.new for e in exact if e.new] + [e.alternative for e in exact if e.alternative]
        expansion += [r["alternative"] for r in method_hits if r.get("alternative")]
        doc_query = "\n".join([query, *expansion])
        scores = self._hybrid(doc_query, DOC_SOURCES, CANDIDATES * width)
        # 메서드 대응표가 지정한 근거 페이지는 그 페이지에서 질의와 가장 맞는 청크를 상위권 점수로 올린다
        # (직접 고른 공식 근거라 후보 순위에 묻히지 않게)
        anchor = max(scores.values(), default=1 / (RRF_K + 1))
        for page in doc_refs:
            best = self.doc_bm25.search(doc_query, 1, only=self.page_doc_idx.get(page, set()))
            if best:
                chunk_id = self.doc_ids[best[0][0]]
                scores[chunk_id] = max(scores.get(chunk_id, 0.0), anchor)

        # ⑤ 규칙 기반 재정렬
        target_keys = {loose_key(e.new) for e in exact if e.new}
        era_weight = ERA_WEIGHT_0X if version_key(target)[0] < 1 else ERA_WEIGHT
        ranked = []
        for chunk_id, score in scores.items():
            if chunk_id in exclude_ids:
                continue
            signals = []
            era = self.chunks[chunk_id]["era"]
            score *= era_weight.get(era, 1.0)
            if era != "1.x":
                signals.append(f"era:{era}")
            if target_keys & self.chunk_import_keys.get(chunk_id, set()):
                score *= IMPORT_LINK_BOOST
                signals.append("uses_target_import")
            if self.chunks[chunk_id]["path"] in doc_refs:
                score *= DOC_REF_BOOST
                signals.append("method_doc_ref")
            ranked.append((chunk_id, score, signals))
        ranked.sort(key=lambda x: -x[1])

        per_page: dict[str, int] = defaultdict(int)
        doc_evidence = []
        for chunk_id, score, signals in ranked:
            page = self.chunks[chunk_id]["path"]
            if per_page[page] >= MAX_PER_PAGE:
                continue
            per_page[page] += 1
            doc_evidence.append(self._doc_evidence(chunk_id, score, signals))
            if len(doc_evidence) >= k * width:
                break

        return map_evidence + method_evidence + doc_evidence


def main():
    parser = argparse.ArgumentParser(description="Query the migration retrieval engine.")
    parser.add_argument("query")
    parser.add_argument("--old", default=None, help="legacy import statement or dotted path")
    parser.add_argument("-k", type=int, default=DEFAULT_K)
    parser.add_argument("--attempt", type=int, default=0)
    parser.add_argument("--target", default=None, help="target langchain version (default: latest)")
    parser.add_argument("--json", action="store_true", help="print full evidence as JSON")
    args = parser.parse_args()

    engine = RetrievalEngine()
    results = engine.retrieve(args.query, old_path=args.old, k=args.k, attempt=args.attempt,
                                target_version=args.target)
    if args.json:
        print(json.dumps([e.to_dict() for e in results], ensure_ascii=False, indent=2))
        return
    for e in results:
        if e.source == "method_map":
            print(f"[{e.match}] {e.evidence_id}  {e.old} {e.signals[0]} → {e.new} ({e.kind})")
        elif e.source == "import_map":
            print(f"[{e.match}] {e.evidence_id}  {e.old} → {e.new} ({e.kind}, {e.import_status})"
                    + (f"  대안: {e.alternative}" if e.alternative else "") + (f"  {e.signals}" if e.signals else ""))
        else:
            print(f"[{e.match} {e.score:.4f}] {e.evidence_id}  ({e.source}, {e.era}) {e.title} > {e.section}"
                    + (f"  {e.signals}" if e.signals else ""))


if __name__ == "__main__":
    main()
