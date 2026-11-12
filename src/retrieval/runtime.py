"""Live knowledge base: lets Pod A's units arrive (or be replaced) while the server runs.

State is one immutable `Bundle` (store + retriever + graph + answerer). A request grabs the current bundle once;
ingest/rebuild build a NEW bundle off to the side and swap it in under a lock, so readers never see a half-built
index. Everything stateful is copied, never shared between bundles.

Ingest is cheap (no LLM): units are validated, indexed, and tagged to concepts by evidence or by BM25 fallback.
New material does not create new concepts until the graph is rebuilt (an LLM job) - `graph_stale` says when.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .answer import GroundedAnswerer
from .calibration import load_threshold
from .config import Settings
from src.graph.graph import KnowledgeGraph, tag_units
from src.graph.graph_builder import GraphBuilder
from .llm import make_llm
from .retriever import HybridRetriever, build_retriever
from .schemas import ConceptNode, ContentUnit
from .store import DEFAULT_CORPUS, DEFAULT_GRAPH, CorpusStore, startup_corpus_path

log = logging.getLogger("pod_b")
MAX_UNITS_PER_INGEST = 2000


@dataclass(frozen=True)
class Bundle:
    store: CorpusStore
    retriever: HybridRetriever
    graph: KnowledgeGraph
    answerer: GroundedAnswerer
    version: int = 0


def prune_graph(graph: KnowledgeGraph, store: CorpusStore) -> dict:
    """Remove evidence pointers to units that no longer exist (e.g. a source was re-uploaded)."""
    pruned_concept_ev = pruned_edge_ev = 0
    for c in graph.concepts.values():
        keep = [u for u in c.evidence_units if store.get(u)]
        pruned_concept_ev += len(c.evidence_units) - len(keep)
        c.evidence_units = keep
        for e in c.prerequisite_edges:
            ek = [u for u in e.evidence_units if store.get(u)]
            pruned_edge_ev += len(e.evidence_units) - len(ek)
            e.evidence_units = ek
    return {"concept_evidence_removed": pruned_concept_ev, "edge_evidence_removed": pruned_edge_ev}


def evidence_coverage_gap(graph: KnowledgeGraph, store: CorpusStore) -> int:
    """Units that no concept lists as evidence (tagged only by the BM25 fallback, or not at all)."""
    covered = {u for c in graph.concepts.values() for u in c.evidence_units}
    return sum(1 for u in store.all() if u.unit_id not in covered)


def load_startup(settings: Settings) -> tuple[CorpusStore, KnowledgeGraph]:
    import os
    corpus = startup_corpus_path(settings.cache_dir)
    store = CorpusStore.from_json(corpus)
    if os.environ.get("POD_B_GRAPH"):
        gpath: Optional[Path] = Path(os.environ["POD_B_GRAPH"])
    elif (Path(settings.cache_dir) / "graph.json").is_file():
        gpath = Path(settings.cache_dir) / "graph.json"
    else:
        gpath = DEFAULT_GRAPH if Path(corpus) == DEFAULT_CORPUS else None  # the demo graph only fits the demo corpus
    graph = KnowledgeGraph.load(gpath) if gpath else KnowledgeGraph([], [])
    prune_graph(graph, store)
    tag_units(graph, store)
    return store, graph


def build_bundle(settings: Settings, store: CorpusStore, graph: KnowledgeGraph,
                 retriever: Optional[HybridRetriever] = None, answerer: Optional[GroundedAnswerer] = None) -> Bundle:
    retriever = retriever or build_retriever(store, settings, graph=graph)
    if answerer is None:
        llm, _ = make_llm(settings)
        strict, perm, cal = load_threshold(Path(settings.cache_dir) / "calibration.json", retriever.backend_key())
        answerer = GroundedAnswerer(retriever, graph, llm, threshold_strict=strict, threshold_permissive=perm,
                                    calibrated=cal, verify_with_llm=settings.verify_with_llm)
    return Bundle(store, retriever, graph, answerer)


class Runtime:
    def __init__(self, bundle: Bundle, settings: Settings, persist: bool = True):
        self._b = bundle
        self.settings, self.persist = settings, persist
        self._lock = threading.RLock()
        self._rebuild = {"state": "idle"}

    @property
    def bundle(self) -> Bundle:
        return self._b

    # ------------------------------------------------------------------ #
    def _swap(self, store: CorpusStore, graph: KnowledgeGraph) -> Bundle:
        old = self._b
        retriever = old.retriever.with_store(store, graph)
        nb = Bundle(store, retriever, graph, old.answerer.with_(retriever, graph), old.version + 1)
        self._b = nb
        return nb

    def _persist(self, store: CorpusStore, graph: KnowledgeGraph) -> None:
        if self.persist:
            cache = Path(self.settings.cache_dir)
            store.save_json(cache / "ingested_corpus.json")
            graph.save(cache / "graph.json")

    def ingest(self, units: list[ContentUnit], replace_sources: bool = True,
               concepts: tuple[ConceptNode, ...] | list[ConceptNode] = ()) -> dict:
        if not units:
            raise ValueError("no units supplied")
        if len(units) > MAX_UNITS_PER_INGEST:
            raise ValueError(f"too many units in one request (max {MAX_UNITS_PER_INGEST})")
        with self._lock:
            old = self._b
            incoming = {u.source_id for u in units}
            keep = [u.model_copy(deep=True) for u in old.store.all()
                    if not (replace_sources and u.source_id in incoming)]
            taken = {u.unit_id: u.source_id for u in keep}
            for u in units:
                if u.unit_id in taken and taken[u.unit_id] != u.source_id:
                    raise ValueError(f"unit_id {u.unit_id!r} is already used by source {taken[u.unit_id]!r}")
                if u.unit_id in taken and not replace_sources:
                    raise ValueError(f"unit_id {u.unit_id!r} already exists (use replace_sources=true to re-ingest)")
            fresh = [u.model_copy(update={"embedding": None, "topic_ids": [], "concept_ids": []}, deep=True)
                     for u in units]
            store = CorpusStore(keep + fresh)  # raises on duplicate ids inside the request
            graph = KnowledgeGraph.from_dict(old.graph.to_dict())
            graph.concepts.update((concept.concept_id, concept) for concept in concepts)
            pruned = prune_graph(graph, store)
            tag = tag_units(graph, store)
            nb = self._swap(store, graph)  # embeds only unseen texts (disk cache), refits BM25/IDF
            self._persist(store, graph)
            gap = evidence_coverage_gap(graph, store)
            log.info("ingest: +%d units from %s -> %d total (v%d)", len(units), sorted(incoming), len(store), nb.version)
            return {"ingested": len(units), "sources": sorted(incoming), "total_units": len(store),
                    "version": nb.version, "graph_pruned": pruned,
                    "tagging": {"auto_tagged": len(tag["auto_tagged"]), "untagged": tag["untagged"]},
                    "graph_stale": gap > 0, "units_without_concept_evidence": gap}

    # ------------------------------------------------------------------ #
    def rebuild_status(self) -> dict:
        with self._lock:
            return dict(self._rebuild)

    def start_graph_rebuild(self, background: bool = True) -> dict:
        with self._lock:
            if self._rebuild.get("state") == "running":
                raise RuntimeError("a graph rebuild is already running")
            llm = self._b.answerer.llm
            if llm is None:
                raise LookupError("no LLM configured (set GEMINI_API_KEY); the graph cannot be rebuilt without one")
            snapshot = self._b
            self._rebuild = {"state": "running", "based_on_version": snapshot.version, "llm": llm.name}
        if background:
            threading.Thread(target=self._run_rebuild, args=(snapshot, llm), daemon=True).start()
        else:
            self._run_rebuild(snapshot, llm)
        return self.rebuild_status()

    def _run_rebuild(self, snapshot: Bundle, llm) -> None:
        try:
            work = CorpusStore(u.model_copy(deep=True) for u in snapshot.store.all())  # builder tags units: use a copy
            res = GraphBuilder(llm).build(work)
            with self._lock:
                if self._b.version != snapshot.version:
                    self._rebuild = {"state": "stale", "message": "the corpus changed while the graph was building; "
                                     "result discarded - run the rebuild again"}
                    return
                self._swap(work, res.graph)
                self._persist(work, res.graph)
                rep = res.report
                self._rebuild = {"state": "done", "concepts": rep["concepts"], "topics": rep["topics"],
                                 "llm_calls": rep["llm_calls"], "edge_validation": rep["edge_validation"],
                                 "cycle_edges_removed": rep["cycle_edges_removed"],
                                 "untagged_units": rep["tagging"]["untagged"],
                                 "integrity_problems": rep["integrity_problems"]}
        except Exception as e:  # noqa: BLE001 - report, never crash the server thread
            log.exception("graph rebuild failed")
            with self._lock:
                self._rebuild = {"state": "failed", "error": str(e)[:300]}
