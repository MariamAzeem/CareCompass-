"""Knowledge base: JSON records + ChromaDB vectors + keyword matching (works in English, Roman Urdu, Urdu)."""
import json
import re
import threading
from typing import Dict, List, Optional

from .config import DATA_DIR

_LOCK = threading.Lock()
_KB: Optional["KnowledgeBase"] = None


def _is_ascii(s: str) -> bool:
    return all(ord(c) < 128 for c in s)


def _phrase_in(phrase: str, text: str) -> bool:
    if len(phrase) < 2:
        return False
    if _is_ascii(phrase):
        return re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", text) is not None
    return phrase in text


def _words(s: str) -> set:
    return set(re.findall(r"[a-z0-9]+|[\u0600-\u06FF]+", s.lower()))


class KnowledgeBase:
    def __init__(self):
        self.records: Dict[str, dict] = {}
        self.collection = None
        self.vector_ok = False
        self.init_error = ""
        data = json.load(open(DATA_DIR / "knowledge_base.json", encoding="utf-8"))
        for r in data["records"]:
            self.records[r["id"]] = r
        self._init_chroma()

    # ---------- vector store ----------
    @staticmethod
    def doc_text(r: dict) -> str:
        return f"{r['care_category']}. {r.get('description', '')} Symptoms: {', '.join(r['symptom_keywords'])}"

    def _init_chroma(self):
        try:
            import chromadb
            client = chromadb.EphemeralClient()
            try:
                client.delete_collection("carecompass_kb")
            except Exception:
                pass
            self.collection = client.create_collection("carecompass_kb", metadata={"hnsw:space": "cosine"})
            self._upsert_vectors(list(self.records.values()))
            self.vector_ok = True
        except Exception as e:  # e.g. the embedding model could not download -> keyword-only mode
            self.vector_ok = False
            self.init_error = str(e)

    def _upsert_vectors(self, recs: List[dict]):
        if self.collection is None or not recs:
            return
        self.collection.upsert(
            ids=[r["id"] for r in recs],
            documents=[self.doc_text(r) for r in recs],
            metadatas=[{"care_category": r["care_category"]} for r in recs],
        )

    # ---------- public API ----------
    def add_records(self, recs: List[dict]):
        """Add (or replace) records, e.g. the ones learned from the web."""
        with _LOCK:
            new = []
            for r in recs:
                if r.get("id") and r["id"] not in self.records:
                    new.append(r)
                self.records[r["id"]] = r
            try:
                self._upsert_vectors(new)
            except Exception as e:
                self.vector_ok = False
                self.init_error = str(e)

    def get(self, rid: str) -> Optional[dict]:
        return self.records.get(rid)

    def _keyword_scores(self, query: str) -> Dict[str, tuple]:
        q = query.lower()
        qw = _words(q)
        out = {}
        for rid, r in self.records.items():
            best, hits = 0.0, 0
            for kw in r["symptom_keywords"]:
                k = kw.lower().strip()
                if not k:
                    continue
                if _phrase_in(k, q):
                    hits += 1
                    best = max(best, 1.0 if (" " in k or len(k) > 5) else 0.8)
                else:
                    kws = _words(k)
                    if len(kws) > 1:
                        ratio = len(kws & qw) / len(kws)
                        if ratio >= 0.5:
                            best = max(best, 0.7 * ratio)
            if best:
                out[rid] = (min(1.0, best), hits)
        return out

    def _vector_scores(self, query: str, n: int) -> Dict[str, float]:
        if not self.vector_ok or self.collection is None:
            return {}
        try:
            res = self.collection.query(query_texts=[query], n_results=min(n, len(self.records)))
            out = {}
            for rid, dist in zip(res["ids"][0], res["distances"][0]):
                sim = 1.0 - float(dist)
                out[rid] = max(0.0, min(1.0, (sim - 0.25) / 0.45))
            return out
        except Exception as e:
            self.vector_ok = False
            self.init_error = str(e)
            return {}

    def search(self, query: str, k: int = 4) -> List[dict]:
        kw = self._keyword_scores(query)
        vec = self._vector_scores(query, k * 3)
        scored = []
        for rid in set(kw) | set(vec):
            a, hits = kw.get(rid, (0.0, 0))
            b = vec.get(rid, 0.0)
            score = min(1.0, max(a, b) + 0.25 * min(a, b))
            rank = score + 0.03 * min(hits, 5)      # more matching words wins a tie
            scored.append({"id": rid, "score": round(score, 3), "rank": rank, "record": self.records[rid]})
        scored.sort(key=lambda x: (-x["rank"], x["id"]))
        return scored[:k]


def get_kb() -> KnowledgeBase:
    global _KB
    with _LOCK:
        if _KB is None:
            _KB = KnowledgeBase()
        return _KB
