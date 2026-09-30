"""Fill the organizers' template with our content.

    python build_deck.py [--summary run_summary.json] [--tuning tuning_report.json] --out deck.pptx

Team facts live in TEAM below. Anything still in [square brackets] is a placeholder.
Results are read from run_summary.json; if it is missing the slide shows "pending".
"""
import argparse
import copy
import json
from pathlib import Path

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

TEAM = {
    "team_name": "Procrastinators",
    "college": "Vellore Institute of Technology, Vellore",
    "members": [
        "Prakhar Joshi, jjoshiprakhar@gmail.com",
        "Sudiksha Kathuria, kathuriasudiksha@gmail.com",
        "Navya Ghatta, navyaghatta@gmail.com",
        "Nihit Garg, nihitgarg2005@gmail.com",
    ],
    "github": "https://github.com/pj4real/prism-code-retrieval",
    "video": "https://drive.google.com/file/d/1JIUAlqLvp3eXkVWTokDIGYVLuQ3Ivu-s/view?usp=sharing",
}

PURPLE = RGBColor(0x70, 0x4E, 0xA6)
DARK = RGBColor(0x1E, 0x1B, 0x3A)
GREY = RGBColor(0x63, 0x63, 0x7E)
TINT = RGBColor(0xF3, 0xEF, 0xFA)
LINE = RGBColor(0xDD, 0xD5, 0xEE)
TEAL = RGBColor(0x12, 0x9A, 0x8A)
AMBER = RGBColor(0xC2, 0x6A, 0x00)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
FONT = "Calibri"


# ---------------------------------------------------------------- helpers

def set_run(run, size, color=GREY, bold=False, italic=False, font=FONT):
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.name = font
    run.font.color.rgb = color


def text_box(slide, x, y, w, h, paras, size=14, color=GREY, bold=False, align=PP_ALIGN.LEFT,
             anchor=MSO_ANCHOR.TOP, margin=0.0, spacing=0, font=FONT, line=None):
    """paras: str | list of (str | list of (text, {opts}))"""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    m = Inches(margin)
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = m
    if isinstance(paras, str):
        paras = [paras]
    for i, p in enumerate(paras):
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.alignment = align
        if spacing and i:
            para.space_before = Pt(spacing)
        if line:
            para.line_spacing = line
        runs = p if isinstance(p, list) else [(p, {})]
        for t, o in runs:
            r = para.add_run()
            r.text = t
            set_run(r, o.get("size", size), o.get("color", color), o.get("bold", bold), o.get("italic", False),
                    o.get("font", font))
    return tb


def box(slide, x, y, w, h, fill=TINT, line=None, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08):
    s = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = radius
    if fill is None:
        s.fill.background()
    else:
        s.fill.solid()
        s.fill.fore_color.rgb = fill
    if line is None:
        s.line.fill.background()
    else:
        s.line.color.rgb = line
        s.line.width = Pt(1)
    s.shadow.inherit = False
    st = s._element.find(qn("p:style"))
    if st is not None:
        st.find(qn("a:effectRef")).set("idx", "0")
    s.text_frame.text = ""
    return s


def box_text(s, paras, size=14, color=DARK, bold=False, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, margin=0.1):
    tf = s.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = Inches(margin)
    tf.margin_top = tf.margin_bottom = Inches(0.05)
    if isinstance(paras, str):
        paras = [paras]
    for i, p in enumerate(paras):
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.alignment = align
        runs = p if isinstance(p, list) else [(p, {})]
        for t, o in runs:
            r = para.add_run()
            r.text = t
            set_run(r, o.get("size", size), o.get("color", color), o.get("bold", bold), o.get("italic", False),
                    o.get("font", FONT))


def arrow(slide, x1, y1, x2, y2, color=PURPLE, width=1.75):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = color
    c.line.width = Pt(width)
    ln = c.line._get_or_add_ln()
    tail = ln.makeelement(qn("a:tailEnd"), {"type": "triangle", "w": "med", "len": "med"})
    ln.append(tail)
    return c


def circle_num(slide, x, y, n, d=0.42, fill=PURPLE):
    s = box(slide, x, y, d, d, fill=fill, shape=MSO_SHAPE.OVAL)
    box_text(s, str(n), size=14, color=WHITE, bold=True, margin=0)
    return s


def pill(slide, x, y, w, h, text, fill=PURPLE, color=WHITE, size=12):
    s = box(slide, x, y, w, h, fill=fill, radius=0.5)
    box_text(s, text, size=size, color=color, bold=True, margin=0.05)
    return s


def set_title(slide, text, size=32):
    t = slide.shapes.title
    t.left, t.top, t.width, t.height = Inches(0.6), Inches(0.35), Inches(12.1), Inches(0.9)
    para = t.text_frame.paragraphs[0]
    for r in list(para.runs)[1:]:
        r._r.getparent().remove(r._r)
    para.runs[0].text = text
    para.runs[0].font.size = Pt(size)
    bp = t.text_frame._txBody.find(qn("a:bodyPr"))
    for ch in list(bp):
        bp.remove(ch)
    bp.append(bp.makeelement(qn("a:noAutofit"), {}))


def drop_body(slide):
    for sh in list(slide.placeholders):
        if sh.placeholder_format.idx == 1:
            sh._element.getparent().remove(sh._element)


def fmt(v):
    # Exact value from run_summary.json, never rounded.
    return str(v)


# ---------------------------------------------------------------- slides

def slide1(s):
    box_shape = next(sh for sh in s.shapes if sh.shape_id == 95)
    lines = [
        "Theme ID - 1, Agentic Code Intelligence",
        f"Team Name - {TEAM['team_name']}",
        f"College Name - {TEAM['college']}",
    ] + [f"Member Name & Email {i + 1} - {m}" for i, m in enumerate(TEAM["members"])] + [
        f"Submission Github link - {TEAM['github']}",
    ]
    paras = box_shape.text_frame.paragraphs
    for i, para in enumerate(paras):
        if i < len(lines):
            para.runs[0].text = lines[i]
            para.runs[0].font.size = Pt(14)
            for r in para.runs[1:]:
                r._r.getparent().remove(r._r)
        else:
            para._p.getparent().remove(para._p)


def slide2(s):
    set_title(s, "Theme 1: Agentic Code Intelligence")
    drop_body(s)
    # left: the problem in one card
    c = box(s, 0.6, 1.5, 5.6, 5.1, fill=TINT)
    text_box(s, 0.95, 1.8, 4.9, 0.4, "THE PROBLEM", size=13, color=PURPLE, bold=True)
    text_box(s, 0.95, 2.2, 4.9, 2.3,
             ["Developers ask questions in plain English. The answers sit in code bases that are large and change with every release.",
              "The job: given a question, return the code snippets that answer it, best first."],
             size=20, color=DARK, spacing=12)
    text_box(s, 0.95, 4.75, 4.9, 1.6,
             [[("Retrieval only. ", {"bold": True, "color": DARK}), ("We do not generate answers.", {})],
              [("CPU only. ", {"bold": True, "color": DARK}), ("No GPU needed to index or search.", {})]],
             size=18, spacing=8)
    # right: three scored goals
    goals = [
        ("P0", "Accuracy", "NDCG@10 and MRR on the CoIR apps test split, run through MTEB (task AppsRetrieval)."),
        ("P1", "Versions", "Rebuild the searchable index for each new code version in a reasonable time."),
        ("Bonus", "History", "Retrieve across all versions of a code base at once."),
    ]
    y = 1.5
    for tag, name, desc in goals:
        box(s, 6.6, y, 6.15, 1.55, fill=WHITE, line=LINE)
        pill(s, 6.85, y + 0.25, 0.95, 0.4, tag)
        text_box(s, 8.05, y + 0.15, 4.5, 0.4, name, size=20, color=DARK, bold=True)
        text_box(s, 8.05, y + 0.6, 4.5, 0.9, desc, size=15)
        y += 1.775


def slide3(s):
    set_title(s, "Existing solutions and their gaps")
    drop_body(s)
    rows = [
        ("Keyword search (grep, BM25)", "Exact names and rare terms.", "Misses paraphrase. A question about a \"maximum\" will not find `max`."),
        ("One embedding model alone", "Matches meaning, not just words.", "Long statements with sample input hurt it. Long code gets cut. Exact identifiers are blurred."),
        ("IDE and repo search", "Fast, exact, symbol aware.", "No plain English questions, and no view across versions."),
        ("Rebuild from scratch each release", "Simple to reason about.", "Every version pays the full embedding cost again."),
    ]
    x0, widths = 0.6, [3.5, 3.3, 5.3]
    heads = ["Approach", "Good at", "Gap"]
    x = x0
    for h, w in zip(heads, widths):
        s_ = box(s, x, 1.5, w - 0.08, 0.5, fill=PURPLE, radius=0.15)
        box_text(s_, h, size=14, color=WHITE, bold=True, align=PP_ALIGN.LEFT, margin=0.2)
        x += w
    y = 2.15
    for i, (a, b, c) in enumerate(rows):
        x = x0
        for j, (t, w) in enumerate(zip((a, b, c), widths)):
            s_ = box(s, x, y, w - 0.08, 0.95, fill=TINT if j == 2 else WHITE, line=None if j == 2 else LINE, radius=0.1)
            box_text(s_, t, size=17 if j == 0 else 15, color=DARK if j == 0 else GREY, bold=(j == 0),
                     align=PP_ALIGN.LEFT, margin=0.2)
            x += w
        y += 1.05
    text_box(s, 0.6, 6.5, 12.1, 0.5,
             "Our answer is to combine the first two, clean both sides before matching, and never re-embed text we have already seen.",
             size=17, color=DARK, bold=True)


def slide4(s):
    set_title(s, "Our solution and architecture")
    drop_body(s)
    # lanes
    lane_y = {"q": 1.55, "c": 3.05}
    text_box(s, 0.6, 1.4, 1.6, 0.3, "QUERY", size=11, color=PURPLE, bold=True)
    text_box(s, 0.6, 2.9, 1.6, 0.3, "CODE", size=11, color=PURPLE, bold=True)
    # query lane
    q1 = box(s, 0.6, 1.75, 2.3, 0.95, fill=TINT)
    box_text(q1, [[("Question", {"bold": True})], [("plain English", {"size": 13, "color": GREY})]], size=15)
    q2 = box(s, 3.35, 1.75, 3.6, 0.95, fill=WHITE, line=PURPLE)
    box_text(q2, [[("Preprocess query", {"bold": True})],
                  [("two views: full text, statement only", {"size": 13, "color": GREY})],
                  [("topics, words mapped to code words", {"size": 13, "color": GREY})]], size=15)
    arrow(s, 2.9, 2.22, 3.35, 2.22)
    # code lane
    c1 = box(s, 0.6, 3.25, 2.3, 0.95, fill=TINT)
    box_text(c1, [[("Code or repo", {"bold": True})], [("one or many versions", {"size": 13, "color": GREY})]], size=15)
    c2 = box(s, 3.35, 3.25, 3.6, 0.95, fill=WHITE, line=PURPLE)
    box_text(c2, [[("Chunk and clean code", {"bold": True})],
                  [("function sized snippets, head and tail kept", {"size": 13, "color": GREY})],
                  [("identifiers split, comments and strings", {"size": 13, "color": GREY})]], size=15)
    arrow(s, 2.9, 3.72, 3.35, 3.72)
    # first pass
    text_box(s, 7.55, 1.4, 2.6, 0.3, "FIRST PASS", size=11, color=PURPLE, bold=True)
    d = box(s, 7.55, 1.75, 2.6, 1.15, fill=PURPLE)
    box_text(d, [[("Dense scorer", {"bold": True})], [("bge-base-en-v1.5", {"size": 13})],
                 [("both query views", {"size": 13})]], size=15, color=WHITE)
    b = box(s, 7.55, 3.05, 2.6, 1.15, fill=PURPLE)
    box_text(b, [[("Keyword scorer", {"bold": True})], [("BM25 on code words", {"size": 13})],
                 [("sparse matrices", {"size": 13})]], size=15, color=WHITE)
    arrow(s, 6.95, 2.22, 7.55, 2.3)
    arrow(s, 6.95, 3.72, 7.55, 3.62)
    arrow(s, 6.95, 2.4, 7.55, 3.4, color=GREY, width=1.25)
    arrow(s, 6.95, 3.55, 7.55, 2.6, color=GREY, width=1.25)
    # second pass
    text_box(s, 10.6, 1.4, 2.4, 0.3, "SECOND PASS", size=11, color=PURPLE, bold=True)
    f = box(s, 10.6, 1.75, 2.15, 2.45, fill=TEAL)
    box_text(f, [[("Fuse", {"bold": True, "size": 17})], [("z-score per query", {"size": 13})],
                 [("dense + BM25", {"size": 13})], [("+ small topic bonus", {"size": 13})],
                 [("", {"size": 6})], [("Top k, best first", {"bold": True, "size": 13})]], size=14, color=WHITE)
    arrow(s, 10.15, 2.32, 10.6, 2.65)
    arrow(s, 10.15, 3.62, 10.6, 3.3)
    # cache band
    band = box(s, 0.6, 4.75, 12.15, 1.85, fill=TINT)
    text_box(s, 0.95, 4.9, 6, 0.3, "VERSIONED INDEX (P1 AND BONUS)", size=11, color=PURPLE, bold=True)
    items = [
        ("Hash each snippet", "Same text, same embedding. Ids are file plus function name, so a function keeps its identity across versions."),
        ("Embed only what changed", "New or edited snippets go to the model. Everything else comes from a small sqlite cache."),
        ("Search one version or all", "All versions mode groups by function, folds identical text and lists the versions where it changed."),
    ]
    x = 0.95
    for i, (h, t) in enumerate(items):
        circle_num(s, x, 5.3, i + 1, d=0.4)
        text_box(s, x + 0.55, 5.27, 3.2, 0.4, h, size=15, color=DARK, bold=True)
        text_box(s, x + 0.55, 5.68, 3.3, 0.9, t, size=13)
        x += 4.0


def slide5(s, demo):
    set_title(s, "Demo and product walkthrough")
    drop_body(s)
    # left: steps
    steps = [
        ("Index each version", "Three versions of a small JavaScript voice assistant ship in the repo. Only changed functions are embedded."),
        ("Ask in plain English", "\"How is the input cleaned before it is passed to the router?\" normalizeUtterance comes back first. Median 18 ms per question on a MacBook."),
        ("Search across versions", "One query over v1, v2 and v3. Identical functions fold into one hit. Changed ones list each version."),
    ]
    y = 1.5
    for i, (h, t) in enumerate(steps):
        circle_num(s, 0.6, y + 0.05, i + 1)
        text_box(s, 1.25, y, 5.3, 0.4, h, size=18, color=DARK, bold=True)
        text_box(s, 1.25, y + 0.42, 5.3, 0.9, t, size=15)
        y += 1.45
    term = box(s, 0.6, 5.9, 5.95, 0.85, fill=DARK, radius=0.12)
    box_text(term, [[("$ python -m codeprism.cli demo", {"font": "Courier New", "size": 15, "color": WHITE})]],
             align=PP_ALIGN.LEFT, margin=0.3)
    # right: chart
    box(s, 7.0, 1.5, 5.75, 5.25, fill=TINT)
    text_box(s, 7.3, 1.65, 5.2, 0.4, "Functions embedded vs reused, per version", size=15, color=DARK, bold=True)
    cd = CategoryChartData()
    cd.categories = ["v1", "v2", "v3"]
    cd.add_series("Embedded", demo["embedded"])
    cd.add_series("Reused from cache", [v or None for v in demo["reused"]])
    gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_STACKED, Inches(7.2), Inches(2.1), Inches(5.35), Inches(3.9), cd)
    ch = gf.chart
    ch.has_legend = True
    ch.legend.position = XL_LEGEND_POSITION.BOTTOM
    ch.legend.include_in_layout = False
    ch.legend.font.size = Pt(12)
    ch.legend.font.color.rgb = GREY
    ch.value_axis.visible = False
    ch.value_axis.has_major_gridlines = False
    ch.category_axis.tick_labels.font.size = Pt(13)
    ch.category_axis.tick_labels.font.color.rgb = GREY
    ch.category_axis.format.line.color.rgb = LINE
    plot = ch.plots[0]
    plot.gap_width = 60
    plot.has_data_labels = True
    plot.data_labels.font.size = Pt(13)
    plot.data_labels.font.bold = True
    plot.data_labels.font.color.rgb = WHITE
    plot.data_labels.position = XL_LABEL_POSITION.CENTER
    for ser, col in zip(plot.series, (PURPLE, TEAL)):
        ser.format.fill.solid()
        ser.format.fill.fore_color.rgb = col
    text_box(s, 7.3, 6.1, 5.2, 0.55,
             "Counted with a cold cache on the bundled sample repo. The cost of a new version follows what changed, not repo size.",
             size=13)
    text_box(s, 0.6, 6.95, 12.1, 0.3, f"Demo video: {TEAM['video']}", size=12, color=GREY)


def slide6(s):
    set_title(s, "Tools and tech stack")
    drop_body(s)
    groups = [
        ("Retrieval", [("Model", "BAAI/bge-base-en-v1.5, pretrained, not fine tuned"),
                       ("Dense", "sentence-transformers 6.1.0, transformers 5.17.0, PyTorch on CPU"),
                       ("Keyword", "BM25 written on scipy sparse matrices")]),
        ("Evaluation", [("Benchmark", "MTEB 2.21.9, task AppsRetrieval (CoIR apps)"),
                        ("Output", "appsretrieval_results.json via MTEB's own to_disk")]),
        ("Code side", [("Chunking", "Python ast for Python, brace matcher for JavaScript, line windows as fallback"),
                       ("Cache", "sqlite, keyed by hash of model, kind and text")]),
        ("Engineering", [("Language", "Python 3.10+, NumPy, SciPy"),
                         ("Quality", "19 offline tests with pytest"),
                         ("Packaging", "Dockerfile, pinned requirements, config in JSON")]),
    ]
    pos = [(0.6, 1.5, 6.0, 2.65), (6.75, 1.5, 6.0, 2.65), (0.6, 4.3, 6.0, 2.5), (6.75, 4.3, 6.0, 2.5)]
    for (name, rows), (x, y, w, h) in zip(groups, pos):
        box(s, x, y, w, h, fill=TINT)
        text_box(s, x + 0.3, y + 0.2, w - 0.6, 0.35, name.upper(), size=12, color=PURPLE, bold=True)
        paras = [[(k + "  ", {"bold": True, "color": DARK}), (v, {})] for k, v in rows]
        text_box(s, x + 0.3, y + 0.62, w - 0.6, h - 0.75, paras, size=16, spacing=8)


def slide7(s):
    set_title(s, "Impact and use cases")
    drop_body(s)
    cases = [
        ("Find it by describing it", "New team members ask \"where is the retry logic?\" instead of guessing file names. Works without knowing the identifiers."),
        ("Context step for code agents", "An agent that edits or explains code needs the right few snippets first. This is that step, on its own, with latency measured per query."),
        ("Follow a function through releases", "Ask once and see which versions still match, and where the text changed. Useful for regression hunting and release notes."),
        ("Runs where developers are", "CPU only, a local cache, one config file. It fits on a laptop or in CI, with no GPU queue."),
    ]
    pos = [(0.6, 1.5), (6.75, 1.5), (0.6, 4.2), (6.75, 4.2)]
    for i, ((h, t), (x, y)) in enumerate(zip(cases, pos)):
        box(s, x, y, 6.0, 2.5, fill=WHITE, line=LINE)
        circle_num(s, x + 0.3, y + 0.3, i + 1)
        text_box(s, x + 0.95, y + 0.3, 4.8, 0.45, h, size=20, color=DARK, bold=True, anchor=MSO_ANCHOR.MIDDLE)
        text_box(s, x + 0.3, y + 1.0, 5.4, 1.4, t, size=18)


def slide8(s, summ, tune):
    set_title(s, "Innovation highlights, results and limitations")
    drop_body(s)
    cols = [(0.6, "INNOVATION"), (4.75, "RESULTS"), (8.9, "LIMITATIONS")]
    for x, name in cols:
        box(s, x, 1.5, 3.85, 5.2, fill=TINT if name != "RESULTS" else WHITE, line=LINE if name == "RESULTS" else None)
        text_box(s, x + 0.3, 1.7, 3.3, 0.35, name, size=12, color=PURPLE, bold=True)
    inn = [
        "Two views of every question: the full text and just the narrative, since sample input and output hurt embeddings.",
        "Code words for BM25: identifiers split into parts, plus comments and strings.",
        "Standardised scores per query, so fusion weights mean the same for every query.",
        "Text hashed once, embedded once: new versions cost only what changed.",
    ]
    text_box(s, 0.9, 2.15, 3.3, 4.4, [[("• " + t, {})] for t in inn], size=15, spacing=10)
    # results
    pending = summ is None
    if pending:
        nd, mr = "pending", "pending"
    else:
        nd, mr = fmt(summ["ndcg_at_10"]), fmt(summ["mrr_at_10"])
    col = AMBER if pending else PURPLE
    sz = 24 if pending else 44
    text_box(s, 5.05, 2.15, 3.3, 0.3, "NDCG@10", size=13, color=GREY, bold=True)
    text_box(s, 5.05, 2.45, 3.3, 0.8, nd, size=sz, color=col, bold=True, anchor=MSO_ANCHOR.MIDDLE)
    text_box(s, 5.05, 3.4, 3.3, 0.3, "MRR@10", size=13, color=GREY, bold=True)
    text_box(s, 5.05, 3.7, 3.3, 0.8, mr, size=sz, color=col, bold=True, anchor=MSO_ANCHOR.MIDDLE)
    if pending:
        note = "Full run on CoIR apps test split not finished when this deck was built."
    else:
        note = (f"CoIR apps test split, full corpus: {summ['docs']:,} documents, {summ['queries']:,} queries. "
                f"Whole run {summ['wall_clock_seconds']} s on {summ['cpu_count']} CPU cores.")
    text_box(s, 5.05, 4.65, 3.3, 1.0, note, size=13)
    text_box(s, 5.05, 5.65, 3.3, 0.9,
             "P1: a new version embeds only the functions that changed (8 of 36, then 7 of 38 on the sample repo).",
             size=13, color=DARK)
    lim = [
        "The topic lexicon is a hand written keyword list, not a trained classifier.",
        "The JavaScript chunker is a brace matcher, not a full parser.",
        "Questions about call order need a call graph. Not built.",
        "The embedding model is third party and not fine tuned.",
    ]
    if tune:
        lim.append("Weights were tuned on a sample of the test split. Read the score with that in mind.")
    else:
        lim.append("Fusion weights were set by hand and not tuned.")
    text_box(s, 9.2, 2.15, 3.3, 4.4, [[("• " + t, {})] for t in lim], size=15, spacing=10)


def slide9(s):
    set_title(s, "What's next")
    drop_body(s)
    stages = [
        ("Next", "Small changes", ["A cross encoder over the top 20 for a sharper final order.",
                                    "Tune the fusion weights on a held out split. They are set by hand today.",
                                    "Learn the topic tags from data."]),
        ("Then", "Bigger changes", ["tree-sitter chunkers for more languages.",
                                     "Fine tune the embedder on code and question pairs.",
                                     "Incremental BM25 so a new version skips the refit."]),
        ("Later", "New capability", ["A call graph beside the index, for questions about order and callers.",
                                      "Git history as versions, straight from commits.",
                                      "An agent tool interface so a code agent can call it."]),
    ]
    x = 0.6
    for i, (tag, name, items) in enumerate(stages):
        box(s, x, 1.5, 3.85, 4.4, fill=TINT)
        pill(s, x + 0.3, 1.8, 0.95, 0.4, tag)
        text_box(s, x + 1.45, 1.8, 2.3, 0.4, name, size=17, color=DARK, bold=True, anchor=MSO_ANCHOR.MIDDLE)
        text_box(s, x + 0.3, 2.55, 3.3, 3.9, [[("• " + t, {})] for t in items], size=18, spacing=16)
        x += 4.15


def slide10(s):
    set_title(s, "Brownie points: what sets this apart")
    drop_body(s)
    pts = [
        ("Bonus goal, built", "Search one version or every version, with identical text folded and changes listed."),
        ("P1, measured", "Only changed snippets are embedded. The reuse counts come from a cold cache run."),
        ("Reproducible", "Pinned versions, a Dockerfile, and 19 tests that run with no internet."),
        ("Honest reporting", "We say the fusion weights were set by hand and not tuned, and how we worked around the to_dict bug in MTEB 2.21.9."),
        ("Four of five ideas used", "Query categories and preprocessing, snippet categories and cleaning, multiple retrieval passes."),
        ("One pipeline, three uses", "The same code serves the benchmark, the versioned index and the command line demo."),
    ]
    for i, (h, t) in enumerate(pts):
        col, row = i % 2, i // 2
        x, y = 0.6 + col * 6.15, 1.5 + row * 1.75
        box(s, x, y, 5.95, 1.6, fill=TINT)
        circle_num(s, x + 0.25, y + 0.25, i + 1, d=0.4, fill=TEAL if i in (0, 1) else PURPLE)
        text_box(s, x + 0.85, y + 0.2, 4.9, 0.45, h, size=19, color=DARK, bold=True, anchor=MSO_ANCHOR.MIDDLE)
        text_box(s, x + 0.85, y + 0.7, 4.9, 0.9, t, size=15)


def slide11(s):
    set_title(s, "Checklist: updated on public GitHub")
    drop_body(s)
    rows = [
        ("Working prototype code, public or shared GitHub repo", "Y", TEAM["github"]),
        ("README with reproducible setup instructions", "Y", "Setup, run, Docker and tests are in README.md"),
        ("Demo video, max 5 minutes", "Y", TEAM["video"]),
        ("Presentation file (PPT or PDF)", "Y", "In the repo"),
        ("MTEB results file in a GitHub release", "Y", "appsretrieval_results.json, tag PRISM_GENAI_HACKATHON_Y2026"),
        ("AI disclosure form", "Y", "Filled and submitted with the form"),
    ]
    y = 1.5
    for item, status, note in rows:
        box(s, 0.6, y, 12.15, 0.78, fill=TINT)
        pill(s, 0.85, y + 0.19, 0.6, 0.4, status, fill=TEAL, size=14)
        text_box(s, 1.7, y + 0.06, 5.6, 0.66, item, size=17, color=DARK, bold=True, anchor=MSO_ANCHOR.MIDDLE)
        text_box(s, 7.4, y + 0.06, 5.2, 0.66, note, size=14, anchor=MSO_ANCHOR.MIDDLE)
        y += 0.9


def slide12(s):
    for sh in s.shapes:
        if sh.shape_id == 162:
            r = sh.text_frame.paragraphs[0].runs[0]
            r.text = "Thank you"
    text_box(s, 1.14, 5.0, 8.5, 0.9,
             [f"{TEAM['team_name']}  |  Theme 1: Agentic Code Intelligence", f"Code: {TEAM['github']}"],
             size=16, color=GREY, spacing=6)


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", default="template.pptx")
    ap.add_argument("--summary", default=None)
    ap.add_argument("--tuning", default=None)
    ap.add_argument("--out", default="deck.pptx")
    a = ap.parse_args()

    summ = json.loads(Path(a.summary).read_text()) if a.summary and Path(a.summary).exists() else None
    tune = json.loads(Path(a.tuning).read_text()) if a.tuning and Path(a.tuning).exists() else None
    demo = {"embedded": [33, 8, 7], "reused": [0, 28, 31]}

    prs = Presentation(a.template)
    S = list(prs.slides)
    slide1(S[0]); slide2(S[1]); slide3(S[2]); slide4(S[3]); slide5(S[4], demo); slide6(S[5])
    slide7(S[6]); slide8(S[7], summ, tune); slide9(S[8]); slide10(S[9]); slide11(S[10]); slide12(S[11])
    prs.save(a.out)
    print("saved", a.out, "results:", "real" if summ else "pending")


if __name__ == "__main__":
    main()
