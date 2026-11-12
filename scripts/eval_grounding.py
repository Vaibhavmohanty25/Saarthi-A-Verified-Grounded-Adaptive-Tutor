"""Development-time evaluation of retrieval + grounding on the labelled queries in pod_b/golden.py.

    python scripts/eval_grounding.py

Works with no LLM (extractive mode) and, if GEMINI_API_KEY is set, also in generative mode.
These are Pod B's own smoke metrics. The team-level framework evaluation (RAGAS/DeepEval) belongs to Pod D and
should call POST /pod-b/ask, which returns `retrieved` (contexts), `answer`, `sources` for exactly that purpose.

CAVEAT: the labelled set is tiny and written by the same author as the corpus/graph; numbers are optimistic.
"""
import json
import os
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.retrieval.answer import GroundedAnswerer  # noqa: E402
from src.retrieval.calibration import load_threshold  # noqa: E402
from src.retrieval.config import Settings  # noqa: E402
from src.retrieval.golden import LEXICAL, NEAR_MISS, OFF_MATERIAL, SEMANTIC  # noqa: E402
from src.graph.graph import KnowledgeGraph  # noqa: E402
from src.retrieval.llm import make_llm  # noqa: E402
from src.retrieval.retriever import build_retriever  # noqa: E402
from src.retrieval.schemas import AnswerStatus  # noqa: E402
from src.retrieval.store import CorpusStore, graph_path  # noqa: E402

s = Settings.from_env()
store = CorpusStore.from_json()
graph = KnowledgeGraph.load(graph_path(s.cache_dir))
retriever = build_retriever(store, s, graph=graph)
strict, perm, calibrated = load_threshold(Path(s.cache_dir) / "calibration.json", retriever.backend_key())
llm, llm_why = make_llm(s)
items = LEXICAL + SEMANTIC


def run(use_llm):
    a = GroundedAnswerer(retriever, graph, llm if use_llm else None, threshold_strict=strict,
                         threshold_permissive=perm, calibrated=calibrated, verify_with_llm=s.verify_with_llm)
    hit1 = hit3 = cit_ok = cit_total = cit_any = prec3 = 0
    answered = 0
    for q, ok in items:
        hits = retriever.search(q, 3)
        ids = [h.unit.unit_id for h in hits]
        hit1 += bool(ids) and ids[0] in ok
        hit3 += any(i in ok for i in ids)
        prec3 += sum(i in ok for i in ids) / 3
        r = a.answer(q)
        if r.status != AnswerStatus.REFUSED:
            answered += 1
            cited = [c.unit_id for c in r.sources]
            cit_total += len(cited)
            cit_ok += sum(i in ok for i in cited)
            cit_any += any(i in ok for i in cited)
    n = len(items)
    refused_off = sum(a.answer(q).status == AnswerStatus.REFUSED for q in OFF_MATERIAL) / len(OFF_MATERIAL)
    nm = [a.answer(q).status for q in NEAR_MISS]
    return {
        "mode": "generative" if use_llm else "extractive",
        "n_in_scope": n, "n_off_topic": len(OFF_MATERIAL), "n_near_miss": len(NEAR_MISS),
        "retrieval_hit@1": round(hit1 / n, 2), "retrieval_hit@3": round(hit3 / n, 2),
        "retrieval_precision@3_strict": round(prec3 / n, 2),
        "in_scope_answered": f"{answered}/{n}",
        "citation_precision": round(cit_ok / cit_total, 2) if cit_total else None,
        "answers_with_a_correct_citation": round(cit_any / answered, 2) if answered else None,
        "off_topic_refusal_rate": round(refused_off, 2),
        "near_miss_not_confidently_grounded": f"{sum(x != AnswerStatus.GROUNDED for x in nm)}/{len(nm)}",
    }


print(f"retrieval: {retriever.backend_key()} | thresholds strict={strict} permissive={perm} calibrated={calibrated}")
results = [run(False)]
if llm is not None:
    print(f"LLM available: {llm.name} ({llm_why}) - running generative mode too")
    results.append(run(True))
else:
    print(f"No LLM ({llm_why}): generative mode skipped.")
for r in results:
    print(json.dumps(r, indent=2))
default_output = Path(__file__).resolve().parents[1] / "src/eval/results/grounding_dev_eval.json"
out = Path(os.getenv("SAARTHI_GROUNDING_RESULTS", str(default_output)))
out.parent.mkdir(parents=True, exist_ok=True)
with NamedTemporaryFile(mode="w", encoding="utf-8", dir=out.parent, delete=False) as tmp:
    json.dump({"backend": retriever.backend_key(), "results": results}, tmp, indent=2)
    tmp.write("\n")
Path(tmp.name).replace(out)
print(f"saved -> {out}")
