#!/usr/bin/env python3
"""Create or update the Helix Support Triage Genie Agent from src/genie/space.json.

Usage:
  python scripts/create_genie_space.py --schema accessdemo.dev_jesus_zaragoza_helix_support \
      --warehouse 2a82c8f87ef698a1 [--space-id <id>] [--ask]

--ask runs the sample questions through the Conversation API and writes the questions,
generated SQL and answers to evidence/06_genie_conversation.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from databricks.sdk import WorkspaceClient

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "src" / "genie" / "space.json"
ID_FILE = ROOT / "src" / "genie" / "space_id.txt"


def _id(kind: str, text: str) -> str:
    return hashlib.md5(f"{kind}:{text}".encode()).hexdigest()


def build_serialized_space(spec: dict, fq: str) -> str:
    sub = lambda s: s.replace("${FQ}", fq)  # noqa: E731
    tables = []
    for t in spec["tables"]:
        entry = {"identifier": f"{fq}.{t['name']}"}
        if t.get("column_configs"):
            entry["column_configs"] = sorted(t["column_configs"], key=lambda c: c["column_name"])
        tables.append(entry)
    payload = {
        "version": 2,
        "config": {"sample_questions": sorted(
            [{"id": _id("sq", q), "question": [q]} for q in spec["sample_questions"]], key=lambda x: x["id"])},
        "data_sources": {"tables": sorted(tables, key=lambda t: t["identifier"])},
        "instructions": {
            "text_instructions": [{"id": _id("ti", "main"), "content": [l + "\n" for l in spec["text_instructions"]]}],
            "example_question_sqls": sorted(
                [{"id": _id("eq", e["question"]), "question": [e["question"]], "sql": [sub(e["sql"])]}
                 for e in spec["example_question_sqls"]], key=lambda x: x["id"]),
        },
        "benchmarks": {"questions": sorted(
            [{"id": _id("bq", b["question"]), "question": [b["question"]],
              "answer": [{"format": "SQL", "content": [sub(b["sql"])]}]} for b in spec["benchmarks"]],
            key=lambda x: x["id"])},
    }
    return json.dumps(payload)


def ask(w: WorkspaceClient, space_id: str, questions: list[str], out: Path) -> None:
    lines = ["# Genie Agent conversation evidence", "",
             f"Space: `{space_id}` (Helix Support Triage). Questions sent through the Genie "
             "Conversation API (`start_conversation_and_wait`); SQL and results are Genie's own output.", ""]
    for q in questions:
        msg = w.genie.start_conversation_and_wait(space_id, q)
        lines += [f"## Q: {q}", "", f"status: `{msg.status.value if msg.status else None}`  "
                  f"conversation: `{msg.conversation_id}`  message: `{msg.message_id}`", ""]
        for att in msg.attachments or []:
            if att.text and att.text.content:
                lines += ["**Genie answer:**", "", att.text.content.strip(), ""]
            if att.query:
                if att.query.description:
                    lines += [f"**Interpretation:** {att.query.description}", ""]
                lines += ["**Generated SQL:**", "", "```sql", att.query.query.strip(), "```", ""]
                res = w.genie.get_message_attachment_query_result(
                    space_id, msg.conversation_id, msg.message_id, att.attachment_id)
                sr = res.statement_response
                cols = [c.name for c in (sr.manifest.schema.columns or [])] if sr and sr.manifest and sr.manifest.schema else []
                rows = (sr.result.data_array or [])[:15] if sr and sr.result else []
                if cols:
                    lines += ["**Result (first 15 rows):**", "", "| " + " | ".join(cols) + " |",
                              "|" + "---|" * len(cols)]
                    lines += ["| " + " | ".join("" if v is None else str(v) for v in r) + " |" for r in rows]
                    lines.append("")
        print(f"asked: {q}")
    out.write_text("\n".join(lines) + "\n")
    print(f"wrote {out}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--schema", required=True, help="catalog.schema holding silver/gold")
    p.add_argument("--warehouse", required=True)
    p.add_argument("--space-id", default=ID_FILE.read_text().strip() if ID_FILE.exists() else "")
    p.add_argument("--ask", action="store_true")
    p.add_argument("--profile", default=os.environ.get("DATABRICKS_CONFIG_PROFILE", "fevm-ai"))
    args = p.parse_args()

    w = WorkspaceClient(profile=args.profile)
    spec = json.loads(SPEC.read_text())
    serialized = build_serialized_space(spec, args.schema)
    if args.space_id:
        space = w.genie.update_space(args.space_id, serialized_space=serialized, title=spec["title"],
                                     description=spec["description"], warehouse_id=args.warehouse)
        print(f"updated Genie space {space.space_id}")
    else:
        space = w.genie.create_space(args.warehouse, serialized, title=spec["title"], description=spec["description"])
        print(f"created Genie space {space.space_id}")
    ID_FILE.write_text(space.space_id + "\n")
    if args.ask:
        ask(w, space.space_id, spec["sample_questions"], ROOT / "evidence" / "06_genie_conversation.md")


if __name__ == "__main__":
    main()
