"""Fill the team placeholders in the deck, the AI disclosure docx and the README.

    pip install python-pptx python-docx
    python submission/fill_placeholders.py submission/team_details.json          # dry run
    python submission/fill_placeholders.py submission/team_details.json --write  # apply

team_details.json (fields left as null are not touched):
{
  "team_name": "CodeSeekers",
  "members": ["Name 2, email", "Name 3, email", null],   # members 2 to 4, null removes the line
  "video": "https://youtu.be/...",
  "submission_date": "30 Sept 2026",
  "review_note": "Reviewed and tested by the team.",       # one note for every feature row
  "representative": {"name": "...", "role": "...", "signature": "...", "date": "30 Sept 2026"},
  "tick_confirmations": true                                 # only if the team read and agrees with all four
}

With --write the files are renamed to VITV_<team>_Submission.pptx and
VITV_<team>_AI_Disclosure.docx and the README links follow. Afterwards it lists any
[bracketed] text that is still left.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from docx import Document
from pptx import Presentation

ROOT = Path(__file__).resolve().parents[1]
SUB = ROOT / "submission"
BRACKET = re.compile(r"\[[^\]]*\]")


def pptx_paragraphs(prs):
    for slide in prs.slides:
        for shape in slide.shapes:
            if shape.has_text_frame:
                yield from shape.text_frame.paragraphs


def docx_paragraphs(doc):
    yield from doc.paragraphs
    for table in doc.tables:
        for row in table.rows:
            seen = set()
            for cell in row.cells:
                if id(cell._tc) in seen:
                    continue
                seen.add(id(cell._tc))
                yield from cell.paragraphs


def replace_runs(paragraphs, mapping, drop):
    """Replace text inside single runs. Paragraphs containing a key in `drop` are removed."""
    changed = 0
    for p in list(paragraphs):
        full = "".join(r.text for r in p.runs)
        if any(k in full for k in drop):
            el = p._p if hasattr(p, "_p") else p._element
            el.getparent().remove(el)
            changed += 1
            continue
        for r in p.runs:
            for old, new in mapping.items():
                if old in r.text:
                    r.text = r.text.replace(old, new)
                    changed += 1
    return changed


def leftovers(paragraphs):
    out = []
    for p in paragraphs:
        out += BRACKET.findall("".join(r.text for r in p.runs))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("details")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    det = json.loads(Path(a.details).read_text())

    team = det.get("team_name")
    common, drop = {}, []
    if team:
        common["[Team name]"] = team
    for i, m in enumerate(det.get("members") or [], start=2):
        key = f"[Member {i} name, email]"
        if m is None:
            drop.append(key)
        else:
            common[key] = m
    if det.get("video"):
        common["[Demo video link]"] = det["video"]

    docmap = dict(common)
    if det.get("submission_date"):
        docmap["[Submission date]"] = det["submission_date"]
    if det.get("review_note"):
        docmap["[Team to state review or changes]"] = det["review_note"]
    rep = det.get("representative") or {}
    for field, key in [("name", "[Name]"), ("role", "[Role]"), ("signature", "[Signature]"), ("date", "[Date]")]:
        if rep.get(field):
            docmap[key] = rep[field]
    if det.get("tick_confirmations") is True:
        docmap["[  ]"] = "[x]"

    deck_path = next(SUB.glob("VITV_*_Submission.pptx"))
    doc_path = next(SUB.glob("VITV_*_AI_Disclosure.docx"))
    prs = Presentation(deck_path)
    doc = Document(doc_path)
    n1 = replace_runs(pptx_paragraphs(prs), common, drop)
    n2 = replace_runs(docx_paragraphs(doc), docmap, [])

    readme = ROOT / "README.md"
    text = readme.read_text()
    if det.get("video"):
        text = text.replace("- Demo video: [Demo video link]", f"- Demo video: {det['video']}")

    print(f"deck: {n1} replacements, disclosure: {n2} replacements")
    if not a.write:
        print("dry run, nothing written. Add --write to apply.")
        return

    safe = re.sub(r"[^A-Za-z0-9]+", "", team) if team else None
    new_deck = SUB / f"VITV_{safe}_Submission.pptx" if safe else deck_path
    new_doc = SUB / f"VITV_{safe}_AI_Disclosure.docx" if safe else doc_path
    prs.save(new_deck)
    doc.save(new_doc)
    if new_deck != deck_path:
        deck_path.unlink()
        text = text.replace(deck_path.name, new_deck.name)
    if new_doc != doc_path:
        doc_path.unlink()
        text = text.replace(doc_path.name, new_doc.name)
    readme.write_text(text)

    # Keep the deck builder in step, so a later rebuild does not bring placeholders back.
    builder = SUB / "build_deck.py"
    b = builder.read_text()
    for old, new in common.items():
        b = b.replace(f'"{old}"', json.dumps(new))
    for key in drop:
        b = b.replace(f'        "{key}",\n', "")
    builder.write_text(b)

    print("wrote", new_deck.relative_to(ROOT), "and", new_doc.relative_to(ROOT))
    left = {
        "deck": leftovers(pptx_paragraphs(Presentation(new_deck))),
        "disclosure": leftovers(docx_paragraphs(Document(new_doc))),
        "README": BRACKET.findall(readme.read_text().split("## Submission materials")[1].split("##")[0]),
    }
    for where, items in left.items():
        items = [x for x in items if x != "[x]" and not x.startswith("[submission") and not x.startswith("[AI_")]
        print(f"left in {where}: {sorted(set(items)) or 'none'}")


if __name__ == "__main__":
    main()
