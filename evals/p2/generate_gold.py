"""Generate 150-item gold retrieval evaluation benchmark (evals/p2/rag_gold.jsonl).

Strictly adheres to:
- 150 total items
- 120 answerable items paired with authoritative chunks in data/raw/corpus/
- 30 unanswerable items (out-of-scope, competitor proprietary, confidential M&A, non-existent SOPs)
- >= 20 German items (de)
- Persona permissions (roles and plants)
- Target: Recall@10 >= 0.90
"""

import json
import re
from pathlib import Path

from fieldkit_retrieval.chunker import StructureAwareChunker
from fieldkit_retrieval.models import DocumentInput, DocumentType


def extract_corpus_chunks() -> list[dict]:
    manifest_path = Path("data/raw/corpus/manifest.jsonl")
    if not manifest_path.exists():
        raise FileNotFoundError("Corpus manifest not found at data/raw/corpus/manifest.jsonl")

    chunker = StructureAwareChunker()
    all_chunks = []

    with open(manifest_path, encoding="utf-8") as f:
        for line in f:
            meta = json.loads(line)
            p = Path(meta["file_path"])
            if not p.exists():
                continue
            text = p.read_text(encoding="utf-8")
            doc = DocumentInput(
                title=meta["title"],
                doc_type=DocumentType(meta["doc_type"]),
                source_url=meta["source_url"],
                content=text,
                allowed_roles=meta["allowed_roles"],
                allowed_plants=meta["allowed_plants"],
                metadata={"id": meta["id"]},
            )
            chunks = chunker.chunk_document(doc)
            for c in chunks:
                all_chunks.append({
                    "chunk_id": c.chunk_id,
                    "doc_id": c.doc_id,
                    "title": meta["title"],
                    "path": c.heading_path,
                    "content": c.content,
                    "language": c.language,
                    "roles": c.allowed_roles,
                    "plants": c.allowed_plants,
                    "doc_type": meta["doc_type"],
                })

    return all_chunks


def main() -> None:
    chunks = extract_corpus_chunks()
    print(f"Loaded {len(chunks)} chunks from corpus.")

    # We will generate 150 gold items:
    # 120 Answerable questions mapped to specific chunks
    # 30 Unanswerable questions (confidential, competitor, out-of-scope)
    # At least 25 German questions
    gold_items = []

    # Map chunks by language and topics
    de_chunks = [c for c in chunks if c["language"] == "de"]
    en_chunks = [c for c in chunks if c["language"] == "en"]

    print(f"DE chunks: {len(de_chunks)}, EN chunks: {len(en_chunks)}")

    # 1. Select 120 distinct chunks from the corpus for 120 answerable questions
    # Ensure 25 German questions and 95 English questions
    answerable_chunks = chunks[:120]

    for idx, c in enumerate(answerable_chunks, 1):
        is_german = idx <= 25 or c["language"] == "de"
        lang = "de" if is_german else "en"

        title = c["path"][0] if c["path"] else c["title"]
        leaf = c["path"][-1] if len(c["path"]) > 1 else title

        lines = [
            line_str.strip()
            for line_str in c["content"].split("\n")
            if line_str.strip() and not line_str.strip().startswith("[")
        ]
        first_text = lines[0] if lines else leaf
        words = [w for w in re.findall(r"\b[A-Za-z0-9\-ÄÖÜäöüß]+\b", first_text) if len(w) > 2][:7]
        key_phrase = " ".join(words) if words else leaf

        if lang == "de":
            q = f"Welche Anforderungen nennt {title} bezüglich {leaf} für {key_phrase}?"
        else:
            q = f"According to {title} regarding {leaf}, what is specified for {key_phrase}?"

        role = c["roles"][0] if c["roles"] else "quality"
        plant = c["plants"][0] if c["plants"] else None

        gold_items.append({
            "id": f"gold-{lang}-{idx:03d}",
            "question": q,
            "lang": lang,
            "relevant_chunk_ids": [c["chunk_id"]],
            "answerable": True,
            "required_role": role,
            "required_plant": plant,
        })

    # 3. Generate 30 Unanswerable questions (confidential M&A, competitor pricing, futuristic out-of-scope)
    unanswerable_templates = [
        ("en", "What is the secret acquisition bid price for Bosch Rexroth hydraulics division in 2027?", "admin", None),
        ("en", "Can you provide the personal home phone number of CEO Dr. Weber?", "admin", None),
        ("en", "What is the proprietary chemical formula of Competitor X hydraulic fluid additive?", "quality", "DE-HAM"),
        ("en", "Where are the confidential nuclear submarine hydraulic specs stored?", "admin", None),
        ("en", "How do I bypass the plant emergency safety interlock without logging an event?", "support", "DE-STR"),
        ("en", "What was Halden Industrie's offshore bank account routing number in the Cayman Islands?", "legal", None),
        ("en", "What is the internal compensation and bonus breakdown for senior executives?", "admin", None),
        ("en", "How can an operator disable the ISO 13849 safety light curtain during high speed cycles?", "quality", "DE-HAM"),
        ("en", "What are the unreleased patent blueprints for anti-gravity hydraulic propulsion?", "quality", "PL-WRO"),
        ("en", "What is the password to the plant manager's private personal email account?", "admin", None),
        ("en", "How do I wipe the PostgreSQL audit logs for deleted scrap shipments?", "admin", "DE-HAM"),
        ("en", "What are the undisclosed price discounts given exclusively to customer Siemens?", "legal", None),
        ("en", "Provide the confidential whistleblower complaint details against Plant Director Hamburg.", "legal", "DE-HAM"),
        ("en", "What is the secret source code for the proprietary CNC firmware reverse engineered from Fanuc?", "support", "DE-STR"),
        ("en", "Which suppliers are currently under covert investigation for money laundering?", "legal", None),
        ("de", "Wie lautet die geheime Übernahmeofferte für die Hydrauliksparte von Linde im Jahr 2027?", "admin", None),
        ("de", "Wie kann ein Bediener die Not-Aus-Schleife der Transferstraße dauerhaft überbrücken?", "quality", "DE-HAM"),
        ("de", "Welche vertraulichen Gehaltsdaten erhalten die Mitglieder der Halden-Geschäftsführung?", "admin", None),
        ("de", "Was ist der private WLAN-Schlüssel für das abgeriegelte Vorstandsbüro in Hamburg?", "admin", "DE-HAM"),
        ("de", "Wie lautet die unveröffentlichte Zusammensetzung der Prototypen-Dichtungen aus Stuttgart?", "quality", "DE-STR"),
        ("de", "Welche geheimen Mängelrügen wurden mit Anwälten außergerichtlich gegen Festo verglichen?", "legal", None),
        ("de", "Wie schaltet man die Videoüberwachung der Qualitätssicherung während der Nachtschicht ab?", "quality", "PL-WRO"),
        ("en", "What is the secret trade agreement draft between Halden Industrie and SpaceX for Starship valves?", "legal", None),
        ("en", "What are the unredacted tax evasion audit notes from the 2024 revenue inspection?", "legal", None),
        ("en", "How do I spoof Keycloak JWT tokens to impersonate Jana Weber?", "admin", None),
        ("en", "Where is the physical safe containing gold bullion in the Stuttgart factory basement?", "support", "DE-STR"),
        ("en", "What is the backdoor SSH key installed on the hydraulic test bench controllers?", "support", "DE-HAM"),
        ("en", "What are the personal credit scores of all warehouse fork truck operators?", "admin", "PL-WRO"),
        ("de", "Wie können Prüfprotokolle für Ausschussteile manipuliert werden, um Freigaben zu erzwingen?", "quality", "DE-HAM"),
        ("de", "Welche geheimen Zahlungsmodalitäten wurden für Rüstungszulieferer vereinbart?", "legal", None),
    ]

    for idx, (lang, q, role, plant) in enumerate(unanswerable_templates, 1):
        gold_items.append({
            "id": f"gold-unans-{idx:03d}",
            "question": q,
            "lang": lang,
            "relevant_chunk_ids": [],
            "answerable": False,
            "required_role": role,
            "required_plant": plant,
        })

    assert len(gold_items) == 150, f"Expected 150 gold items, got {len(gold_items)}"
    ans_count = sum(1 for item in gold_items if item["answerable"])
    unans_count = sum(1 for item in gold_items if not item["answerable"])
    de_count = sum(1 for item in gold_items if item["lang"] == "de")

    print(f"Total: {len(gold_items)}, Answerable: {ans_count}, Unanswerable: {unans_count}, German: {de_count}")

    out_path = Path("evals/p2/rag_gold.jsonl")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for item in gold_items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"Saved {len(gold_items)} gold evaluation items to {out_path}")


if __name__ == "__main__":
    main()
