"""
seed_kb.py
Optional one-time script: loads knowledge_base/sample_kb.txt into the
database as KB entries (split by blank-line sections) and builds the
FAISS index. Run this once after setup so the chatbot has something
to answer questions from immediately.

Usage: python seed_kb.py
"""

import database as db
import rag_pipeline as rag

db.init_db()

with open("knowledge_base/sample_kb.txt", "r") as f:
    raw = f.read()

sections = [s.strip() for s in raw.split("\n\n") if s.strip()]

for section in sections:
    lines = section.split("\n")
    title = lines[0].replace(":", "").strip()
    content = section
    db.add_kb_entry(title, content, source="manual")

entries = db.get_all_kb_entries()
rag.build_index_from_kb_entries(entries)

print(f"Seeded {len(entries)} KB entries and built the FAISS index.")
