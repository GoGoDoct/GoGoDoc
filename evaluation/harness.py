"""RAG 골든 평가 코어 - 데이터셋 로드·결정적 채점·지표 산출·기록

CLI(eval_rag.py)·대시보드(dashboard.py)·회귀 테스트(tests/)가 공통으로 import 한다
"""

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# evaluation/ 기준 경로
_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
GOLDEN_PATH = _HERE / "datasets" / "rag_golden.jsonl"
HISTORY_PATH = _HERE / "history" / "runs.jsonl"

# 저장소 루트를 import 경로에 추가 - 어디서 실행하든 gogodoc import 가능
import sys

if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gogodoc.domain.services.normalization import canonicalize
from gogodoc.domain.services.classification import classify
from gogodoc.domain.reference import reference_dict


def load_cases(path: Path = GOLDEN_PATH) -> list[dict]:
    """JSONL 골든 케이스 로드"""
    cases = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            cases.append(json.loads(line))
    return cases


def build_retriever(kind: str | None = None):
    """RETRIEVER 환경변수 또는 인자에 따라 리트리버 생성 - 기본 dict"""
    kind = (kind or os.getenv("RETRIEVER", "dict")).lower()
    if kind == "pgvector":
        from gogodoc.infrastructure.config import load_settings
        from gogodoc.infrastructure.retrieval.embedder import OpenAIEmbedder
        from gogodoc.infrastructure.retrieval.pgvector_retriever import PgvectorRetriever

        s = load_settings()
        embedder = OpenAIEmbedder(api_key=s.openai_api_key, model=s.embed_model)
        return PgvectorRetriever(s.database_url, embedder), "pgvector"
    from gogodoc.infrastructure.retrieval.dict_retriever import DictRetriever

    return DictRetriever(), "dict"


def eval_deterministic(cases: list[dict], retriever) -> list[dict]:
    """정규화·검색·분류 결정적 채점 - 케이스별 결과 row 리스트 반환"""
    rows = []
    for c in cases:
        exp = c["expected"]
        prof = c["profile"]

        got_canon, score, matched = canonicalize(c["raw_name"])
        entry = retriever.retrieve(got_canon)
        got_hit = entry is not None
        got_flag = classify(got_canon, c["value"], prof["sex"], prof["age"]).value

        norm_ok = got_canon == exp["canonical_name"]
        hit_ok = got_hit == exp["retrieval_hit"]
        flag_ok = got_flag == exp["flag"]
        src_ok = (not got_hit) or entry.get("source") == exp["grounding_source"]

        # 검색 정답률 - "올바른 엔트리" 기준 (boolean 적중과 구분)
        retr_correct = (exp["retrieval_hit"] and got_hit and norm_ok) or (
            not exp["retrieval_hit"] and not got_hit
        )
        # 오적중 - 가져오면 안 되거나(OOV) 엉뚱한 표준명을 가져옴
        false_pos = got_hit and (not exp["retrieval_hit"] or not norm_ok)

        rows.append(
            {
                "id": c["id"],
                "raw": c["raw_name"],
                "intent": c["intent"],
                "known_gap": c.get("known_gap", False),
                "norm_ok": norm_ok,
                "hit_ok": hit_ok,
                "retr_correct": retr_correct,
                "false_pos": false_pos,
                "flag_ok": flag_ok,
                "src_ok": src_ok,
                "all_ok": norm_ok and hit_ok and flag_ok and src_ok,
                "got": {"canon": got_canon, "hit": got_hit, "flag": got_flag, "score": score},
                "exp": {
                    "canon": exp["canonical_name"],
                    "hit": exp["retrieval_hit"],
                    "flag": exp["flag"],
                },
            }
        )
    return rows


def metrics_for(rows: list[dict]) -> dict:
    """row 묶음의 집계 지표 - 비율은 0~1, false_pos 는 건수"""
    n = len(rows)
    if not n:
        return {"n": 0}
    return {
        "n": n,
        "normalization": sum(r["norm_ok"] for r in rows) / n,
        "retrieval_correct": sum(r["retr_correct"] for r in rows) / n,
        "false_pos": sum(r["false_pos"] for r in rows),
        "classification": sum(r["flag_ok"] for r in rows) / n,
        "source": sum(r["src_ok"] for r in rows) / n,
        "all_pass": sum(r["all_ok"] for r in rows) / n,
    }


def eval_retrieval_direct(cases: list[dict], retriever) -> list[dict]:
    """RAG 전용 경로 채점 - 정규화 없이 원본명을 그대로 retriever 에 투입

    벡터 검색이 변형명을 해소하고 OOV 를 임계값으로 거르는지 직접 측정한다
    dict 리트리버로 돌리면 변형명이 전부 miss 로 떨어져 RAG 와의 대비가 드러난다
    """
    rows = []
    for c in cases:
        exp = c["expected"]
        entry = retriever.retrieve(c["raw_name"])
        got_hit = entry is not None
        want_entry = reference_dict.lookup(exp["canonical_name"]) if exp["retrieval_hit"] else None

        if exp["retrieval_hit"]:
            correct = got_hit and entry == want_entry
        else:
            correct = not got_hit  # OOV - 거르는 게 정답
        false_pos = got_hit and (not exp["retrieval_hit"] or entry != want_entry)

        rows.append(
            {
                "id": c["id"],
                "raw": c["raw_name"],
                "intent": c["intent"],
                "known_gap": c.get("known_gap", False),
                "oov": not exp["retrieval_hit"],
                "correct": correct,
                "false_pos": false_pos,
                "got_hit": got_hit,
            }
        )
    return rows


def probe(raw_name: str, value: float | None, sex: str, age: int, retriever) -> dict:
    """단건 테스트 - 임의 항목명에 대한 정규화·검색(파이프라인/RAG전용)·분류 결과

    파이프라인 경로: canonicalize(raw) → retrieve(canonical)
    RAG 전용 경로: retrieve(raw) - 정규화 우회, 원본명 직접 검색
    """
    canon, score, matched = canonicalize(raw_name)
    pipe_entry = retriever.retrieve(canon)
    direct_entry = retriever.retrieve(raw_name)
    flag = classify(canon, value, sex, age).value
    rng = reference_dict.select_range(pipe_entry, sex, age) if pipe_entry else None
    return {
        "raw_name": raw_name,
        "canonical": canon,
        "score": score,
        "matched": matched,
        "flag": flag,
        "reference_range": rng,
        "pipeline": pipe_entry,
        "direct": direct_entry,
    }


def direct_metrics(rows: list[dict]) -> dict:
    """RAG 전용 경로 집계 - 검색 정답률·오적중·OOV 차단율"""
    n = len(rows)
    if not n:
        return {"n": 0}
    oov = [r for r in rows if r["oov"]]
    return {
        "n": n,
        "retrieval_correct": sum(r["correct"] for r in rows) / n,
        "false_pos": sum(r["false_pos"] for r in rows),
        "oov_n": len(oov),
        "oov_rejected": (sum(not r["got_hit"] for r in oov) / len(oov)) if oov else None,
    }


def split_core_gap(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """핵심 회귀 케이스와 known_gap 케이스 분리"""
    core = [r for r in rows if not r["known_gap"]]
    gap = [r for r in rows if r["known_gap"]]
    return core, gap


def _git_sha() -> str:
    """현재 커밋 short SHA - 실패 시 unknown"""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=_ROOT,
            capture_output=True,
            text=True,
            timeout=3,
        )
        return out.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def run(kind: str | None = None, cases: list[dict] | None = None) -> dict:
    """평가 1회 실행 - 케이스별 row 와 핵심/gap 집계 요약 반환 (기록·출력 없음)"""
    cases = cases if cases is not None else load_cases()
    retriever, used_kind = build_retriever(kind)
    rows = eval_deterministic(cases, retriever)
    core, gap = split_core_gap(rows)
    return {
        "retriever": used_kind,
        "dataset": GOLDEN_PATH.name,
        "n_cases": len(cases),
        "core": metrics_for(core),
        "gap": metrics_for(gap),
        "rows": rows,
    }


def record_run(
    summary: dict, gen: dict | None = None, direct: dict | None = None, path: Path = HISTORY_PATH
) -> dict:
    """실행 요약을 history/runs.jsonl 에 한 줄 추가 (시계열 누적) - 기록 객체 반환"""
    record = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_sha": _git_sha(),
        "retriever": summary["retriever"],
        "dataset": summary["dataset"],
        "n_cases": summary["n_cases"],
        "core": summary["core"],
        "gap": summary["gap"],
        "direct": direct,
        "gen": gen,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def load_history(path: Path = HISTORY_PATH) -> list[dict]:
    """누적 실행 기록 로드 (시간순)"""
    p = Path(path)
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out
