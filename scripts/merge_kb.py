"""Merge the three KB files into data/knowledge_base.json and remove duplicates.

Run:  python scripts/merge_kb.py

Rules
- Same id, or an entry in ALIASES  -> the same condition: merged into one record.
- The merged record keeps the richest base, unions keywords / red flags / tests,
  and keeps the MORE URGENT urgency (the safer choice).
- Broad symptom-level entries (fever_adult, chest_pain...) are intentionally kept
  next to condition-level ones: they catch vague user wording.
"""
import json
import re
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
SOURCES = [
    ("a", "_src_a_kb_symptoms.json"),
    ("b", "_src_b_additional_33.json"),
    ("c", "_src_c_draft_21.json"),
]
ALIASES = {  # duplicate id -> canonical id
    "hypertension": "high_blood_pressure",
    "indigestion": "heartburn_acid_reflux",
    "eczema": "atopic_eczema",
    "influenza": "flu",
    "anaemia": "iron_deficiency_anaemia",
    "piles_haemorrhoids": "piles",
}
RANK = {"routine": 0, "urgent": 1, "emergency": 2}
LIST_FIELDS = ["symptom_keywords", "red_flags", "baseline_tests"]
REQUIRED = ["id", "symptom_keywords", "care_category", "urgency", "red_flags", "specialist", "baseline_tests"]


def uniq(items):
    seen, out = set(), []
    for x in items:
        clean = re.sub(r"\s+", " ", str(x)).strip()
        key = clean.lower()
        if key and key not in seen:
            seen.add(key)
            out.append(clean)
    return out


def richness(r):
    score = len(r.get("description", "")) + 10 * sum(len(r.get(f, [])) for f in LIST_FIELDS)
    return score + (50 if "nhs.uk" in r.get("source", "") else 0)


def merge(base, other):
    out = dict(base)
    for f in LIST_FIELDS:
        out[f] = uniq(list(base.get(f, [])) + list(other.get(f, [])))
    if RANK[other["urgency"]] > RANK[base["urgency"]]:
        out["urgency"] = other["urgency"]
    for f in ["description", "alt_specialist", "age_notes", "gender_notes"]:
        if not out.get(f) and other.get(f):
            out[f] = other[f]
    out["source"] = " | ".join(uniq([base.get("source", ""), other.get("source", "")]))
    return out


def main():
    pool, log, total_in = {}, [], 0
    for tag, fname in SOURCES:
        recs = json.load(open(DATA / fname, encoding="utf-8"))["records"]
        total_in += len(recs)
        for r in recs:
            r = dict(r)
            r["id"] = ALIASES.get(r["id"], r["id"])
            missing = [k for k in REQUIRED if k not in r]
            if missing:
                print("SKIP (missing fields)", r.get("id"), missing)
                continue
            if r["urgency"] not in RANK:
                print("SKIP (bad urgency)", r["id"])
                continue
            if r["id"] in pool:
                old = pool[r["id"]]
                base, other = (old, r) if richness(old) >= richness(r) else (r, old)
                pool[r["id"]] = merge(base, other)
                log.append(f"merged duplicate '{r['id']}' (from source {tag})")
            else:
                pool[r["id"]] = r

    records = []
    for r in pool.values():
        r.setdefault("alt_specialist", "")
        r.setdefault("age_notes", "")
        r.setdefault("gender_notes", "")
        if not r.get("description"):
            kws = [k for k in r["symptom_keywords"] if re.match(r"^[\x00-\x7f]+$", k)][:8]
            r["description"] = f"{r['care_category']}. Common words people use: {', '.join(kws)}."
        r["origin"] = "curated"
        records.append(r)
    records.sort(key=lambda x: x["id"])

    out = {
        "_meta": {
            "status": "Merged and de-duplicated. Informational only, not a diagnosis. Must be clinically reviewed before real-world use.",
            "record_count": len(records),
            "attribution": "Information from the NHS website is licensed under the Open Government Licence v3.0.",
        },
        "records": records,
    }
    json.dump(out, open(DATA / "knowledge_base.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"input records: {total_in} -> unique records: {len(records)} ({total_in - len(records)} duplicates removed)")
    print("\n".join(log))
    print("emergency:", [r["id"] for r in records if r["urgency"] == "emergency"])


if __name__ == "__main__":
    sys.exit(main())
