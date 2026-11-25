"""Patches the live Google Doc to match docs/paper/build_doc.py, without rebuilding it.

    python3 docs/paper/patch_doc.py content READ.json > batch.json   # step 1: text, tables, figures
    PATCH_CHUNKS=3 OUT=dir python3 docs/paper/patch_doc.py content READ.json  # step 1 in 3 batches
    python3 docs/paper/patch_doc.py style READ.json > batch.json     # step 2 (fresh read): styles
    python3 docs/paper/patch_doc.py check READ.json                  # report what still differs

READ.json is a fresh read_doc of the doc. Each step prints one update_doc request body (JSON, with the
read's revision as requiredRevisionId) and a summary on stderr. Send step 1, read again, send step 2,
read again and run check.

How it works: the doc and the generator are both turned into a list of units (a paragraph; a table with
its caption; a figure with its caption) and aligned with difflib. Then, for units that differ:
  - a paragraph whose wording changed: replaceAllText on the smallest unique span that changed
  - a paragraph or unit that is new or gone: inserted after the previous unit, or deleted
  - a table: columns or rows removed with deleteTableColumn/deleteTableRow when that is the only change,
    single cells rewritten, otherwise the table is deleted and inserted again (build_doc.table_requests)
  - a figure whose file changed: the image is replaced
  - a caption whose number changed: the number is rewritten in place
Index-based edits are applied bottom-up in one batch, so every edit can use the positions of the one read.
Step 2 compares every paragraph's style with what build_doc would set and fixes the ones that differ.
"""
import difflib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_doc as nb  # noqa: E402  (the target version)

nb.layout()
u16 = nb.u16
rng = nb.rng


# ---------------------------------------------------------------- reading the doc
def load_doc(path):
    doc = json.load(open(path))
    while isinstance(doc, dict) and "content" in doc and not isinstance(doc.get("content"), list):
        doc = doc["content"]
    return doc


def ptext(par):
    out = []
    for e in par["elements"]:
        if "textRun" in e:
            out.append(e["textRun"]["content"])
        elif "inlineObjectElement" in e:
            out.append("￼")
    return "".join(out)


def doc_units(doc):
    """Units of the live doc: dicts with type P/T/F, key, text, ranges and the raw elements."""
    body = doc["tabs"][0]["documentTab"]["body"]["content"]
    inl = doc["tabs"][0]["documentTab"].get("inlineObjects", {})
    units, i = [], 0
    while i < len(body):
        el = body[i]
        if "paragraph" not in el:
            i += 1
            continue
        t = ptext(el["paragraph"])
        txt = t.rstrip("\n")
        if not txt:
            i += 1
            continue
        if txt == "￼":                       # figure: image paragraph + caption paragraph
            obj = [e for e in el["paragraph"]["elements"] if "inlineObjectElement" in e][0]
            oid = obj["inlineObjectElement"]["inlineObjectId"]
            uri = inl[oid]["inlineObjectProperties"]["embeddedObject"].get("imageProperties", {}).get("sourceUri", "")
            j = i + 1
            while "paragraph" not in body[j] or not ptext(body[j]["paragraph"]).strip():
                j += 1
            cap = ptext(body[j]["paragraph"]).rstrip("\n")
            units.append(dict(type="F", key="F|" + re.sub(r"^Fig\. \d+: ", "", cap), cap=cap, uri=uri,
                              img=obj["startIndex"], start=el["startIndex"], end=body[j]["endIndex"],
                              cap_start=body[j]["startIndex"], cap_end=body[j]["endIndex"]))
            i = j + 1
            continue
        if re.match(r"TABLE [IVXL]+: ", txt) and i + 1 < len(body) and "table" in body[i + 1]:
            tab = body[i + 1]
            rows = [[ptext(c["content"][0]["paragraph"]).rstrip("\n") if len(c["content"]) == 1 else
                     "".join(ptext(p["paragraph"]) for p in c["content"] if "paragraph" in p).rstrip("\n")
                     for c in r["tableCells"]] for r in tab["table"]["tableRows"]]
            trail = body[i + 2] if i + 2 < len(body) and "paragraph" in body[i + 2] else None
            units.append(dict(type="T", key="T|" + re.sub(r"^TABLE [IVXL]+: ", "", txt), cap=txt, rows=rows,
                              table=tab, start=el["startIndex"], cap_end=el["endIndex"],
                              tstart=tab["startIndex"], tend=tab["endIndex"],
                              end=trail["endIndex"] if trail is not None and not ptext(trail["paragraph"]).strip()
                              else tab["endIndex"]))
            i += 2
            continue
        units.append(dict(type="P", key=txt, text=txt, start=el["startIndex"], end=el["endIndex"], el=el))
        i += 1
    return units


def gen_units():
    """Units of the target version, from build_doc's blocks."""
    units, i = [], 0
    B = nb.B
    while i < len(B):
        b = B[i]
        if b["kind"] == "tcap":
            units.append(dict(type="T", key="T|" + re.sub(r"^TABLE [IVXL]+: ", "", b["plain"]), cap=b["plain"],
                              tkey=b["table"], rows=[[str(x) for x in r] for r in nb.T[b["table"]][1]], block=b))
            i += 1
        elif b["kind"] == "fig":
            cap = B[i + 1]
            units.append(dict(type="F", key="F|" + re.sub(r"^Fig\. \d+: ", "", cap["plain"]), cap=cap["plain"],
                              fkey=b["figure"], uri=nb.RAW + nb.FIGS[b["figure"]][0], block=b, capblock=cap))
            i += 2
        else:
            units.append(dict(type="P", key=b["plain"], text=b["plain"], block=b))
            i += 1
    return units


# ---------------------------------------------------------------- helpers
def minimal_spans(a, b, haystack, gap=40):
    """(old, new) pairs of substrings that turn a into b, one per cluster of nearby changes, each
    occurring once in haystack. Changes far apart get separate replacements, so the text between
    them (and any link or other inline style it carries) is not rewritten."""
    m = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    ops = [o for o in m.get_opcodes() if o[0] != "equal"]
    clusters = []
    for o in ops:
        if clusters and o[1] - clusters[-1][2] < gap:
            clusters[-1] = (clusters[-1][0], clusters[-1][1], o[2], clusters[-1][3], o[4])
        else:
            clusters.append((o[0], o[1], o[2], o[3], o[4]))
    out, prev_hi = [], 0
    for k, (_, lo, hi, lo2, hi2) in enumerate(clusters):
        nxt = clusters[k + 1][1] if k + 1 < len(clusters) else len(a)
        while True:
            old = a[lo:hi]
            if len(old) >= min(20, nxt - prev_hi) and haystack.count(old) == 1:
                break
            if lo > prev_hi:
                lo, lo2 = lo - 1, lo2 - 1
            elif hi < nxt:
                hi, hi2 = hi + 1, hi2 + 1
            else:
                sys.exit(f"no unique span for a change in {a[:60]!r}")
        out.append((a[lo:hi], b[lo2:hi2]))
        prev_hi = hi
    return out


def fig_size(key):
    path, width, w, h, _ = nb.FIGS[key]
    return {"width": nb.pt(width), "height": nb.pt(round(width * h / w, 1))}


def table_delete_range(u):
    """Range that removes a table and the empty paragraph after it (the caption's newline stays)."""
    return rng(u["tstart"], u["end"])


# ---------------------------------------------------------------- step 1: content
def content(doc):
    du, gu = doc_units(doc), gen_units()
    rev = doc["revisionId"]
    full = "".join(u.get("text", u.get("cap", "")) + "\n" for u in du)
    groups, repl, notes, inserted_text = [], [], [], []

    def insert_after(anchor_end, new_units):
        """Insert new units after the paragraph/unit that ends at anchor_end (its last newline)."""
        at = anchor_end - 1
        reqs, pos = [], at
        text = ""
        for u in new_units:
            if u["type"] == "F":
                sys.exit("inserting a new figure is not handled; add it to patch_doc.py")
            t = u["cap"] if u["type"] == "T" else u["text"]
            text += "\n" + t
        reqs.append({"insertText": {"location": {"index": at}, "text": text}})
        inserted_text.append(text)
        # tables, bottom-up: each caption's newline is at the end of its text
        p = at + 1
        cap_ends = []
        for u in new_units:
            t = u["cap"] if u["type"] == "T" else u["text"]
            p_end = p + u16(t)                    # index of this paragraph's newline after the insert
            if u["type"] == "T":
                cap_ends.append((p_end, u["tkey"]))
            p = p_end + 1
        for p_end, key in reversed(cap_ends):
            reqs += nb.table_requests(key, p_end)
        groups.append((at, reqs))
        notes.append(f"insert after index {at}: {[u['type'] + ':' + (u.get('tkey') or u.get('text', '')[:40]) for u in new_units]}")

    body_end = doc["tabs"][0]["documentTab"]["body"]["content"][-1]["endIndex"]

    def delete_units(units):
        for u in units:
            end = min(u["end"], body_end - 1)       # the body's last newline cannot be deleted
            groups.append((u["start"], [{"deleteContentRange": {"range": rng(u["start"], end)}}]))
            notes.append(f"delete {u['type']}: {u['key'][:60]}")

    def update_table(d, g):
        old, new = d["rows"], g["rows"]
        reqs, S = [], d["tstart"]
        key = g["tkey"]
        widths = nb.T[key][2]
        if old == new:
            pass
        elif len(old[0]) > len(new[0]) and len(old) == len(new):
            keep = [c for c in range(len(old[0])) if old[0][c] in new[0]]
            gone = [c for c in range(len(old[0])) if c not in keep]
            if [[r[c] for c in keep] for r in old] != new:
                return recreate_table(d, g)
            for c in sorted(gone, reverse=True):
                reqs.append({"deleteTableColumn": {"tableCellLocation": {"tableStartLocation": {"index": S},
                                                                         "rowIndex": 0, "columnIndex": c}}})
            for c, w in enumerate(widths):
                reqs.append({"updateTableColumnProperties": {"tableStartLocation": {"index": S}, "columnIndices": [c],
                                                             "tableColumnProperties": {"widthType": "FIXED_WIDTH",
                                                                                       "width": nb.pt(w)},
                                                             "fields": "widthType,width"}})
            notes.append(f"table {key}: delete columns {gone}")
        elif len(old) > len(new) and len(old[0]) == len(new[0]) and all(r in old for r in new):
            gone = [i for i, r in enumerate(old) if r not in new]
            if [r for i, r in enumerate(old) if i not in gone] != new:
                return recreate_table(d, g)
            for i in sorted(gone, reverse=True):
                reqs.append({"deleteTableRow": {"tableCellLocation": {"tableStartLocation": {"index": S},
                                                                      "rowIndex": i, "columnIndex": 0}}})
            notes.append(f"table {key}: delete rows {gone}")
        elif len(old) == len(new) and len(old[0]) == len(new[0]):
            cells = d["table"]["table"]["tableRows"]
            edits = []
            for r in range(len(old)):
                for c in range(len(old[0])):
                    if old[r][c] != new[r][c]:
                        par = cells[r]["tableCells"][c]["content"][0]
                        a, z = par["startIndex"], par["endIndex"] - 1
                        edits.append((a, z, new[r][c], r == 0))
            for a, z, t, head in sorted(edits, reverse=True):
                if z > a:
                    reqs.append({"deleteContentRange": {"range": rng(a, z)}})
                if t:                                  # an emptied cell needs no insert
                    reqs.append({"insertText": {"location": {"index": a}, "text": t}})
                    reqs.append({"updateTextStyle": {"range": rng(a, a + u16(t)), "textStyle": {
                        "weightedFontFamily": nb.FONT, "fontSize": nb.pt(8), "bold": head, "italic": False},
                        "fields": "weightedFontFamily,fontSize,bold,italic"}})
            notes.append(f"table {key}: {len(edits)} cells rewritten")
        else:
            return recreate_table(d, g)
        if reqs:
            groups.append((S, reqs))

    def recreate_table(d, g):
        reqs = [{"deleteContentRange": {"range": table_delete_range(d)}}]
        reqs += nb.table_requests(g["tkey"], d["cap_end"] - 1)
        groups.append((d["tstart"], reqs))
        notes.append(f"table {g['tkey']}: recreated")

    def renumber(d, g):
        old = re.match(r"^(TABLE [IVXL]+: |Fig\. \d+: )", d["cap"]).group(1)
        new = re.match(r"^(TABLE [IVXL]+: |Fig\. \d+: )", g["cap"]).group(1)
        if old != new:
            a = d["start"] if d["type"] == "T" else d["cap_start"]
            groups.append((a, [{"deleteContentRange": {"range": rng(a, a + u16(old))}},
                               {"insertText": {"location": {"index": a}, "text": new}}]))
            notes.append(f"renumber {old.strip()} -> {new.strip()}")

    sm = difflib.SequenceMatcher(a=[u["key"] for u in du], b=[u["key"] for u in gu], autojunk=False)
    pending_rewords = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for d, g in zip(du[i1:i2], gu[j1:j2]):
                if d["type"] == "T":
                    renumber(d, g)
                    update_table(d, g)
                elif d["type"] == "F":
                    renumber(d, g)
                    if d["uri"] != g["uri"]:
                        groups.append((d["img"], [{"deleteContentRange": {"range": rng(d["img"], d["img"] + 1)}},
                                                  {"insertInlineImage": {"uri": g["uri"], "location": {"index": d["img"]},
                                                                         "objectSize": fig_size(g["fkey"])}}]))
                        notes.append(f"figure {g['fkey']}: new image")
            continue
        olds, news = du[i1:i2], gu[j1:j2]
        # pair changed units by similarity, in order (same type only)
        pairs, used, k = [], set(), 0
        for gi, g in enumerate(news):
            best, bi = 0.0, None
            for di in range(k, len(olds)):
                d = olds[di]
                if d["type"] != g["type"] or di in used:
                    continue
                r = difflib.SequenceMatcher(a=d["key"], b=g["key"], autojunk=False).ratio()
                if r > best:
                    best, bi = r, di
            if bi is not None and best >= 0.6:
                pairs.append((bi, gi))
                used.add(bi)
                k = bi + 1
        paired_new = {gi: bi for bi, gi in pairs}
        for bi, gi in pairs:
            d, g = olds[bi], news[gi]
            if d["type"] == "P":
                pending_rewords.append((d["text"], g["text"]))
            elif d["type"] == "T":
                renumber(d, g)
                if d["key"] != g["key"]:
                    pending_rewords.append((d["cap"], g["cap"]))
                update_table(d, g)
            else:
                if d["key"] != g["key"]:
                    pending_rewords.append((d["cap"], g["cap"]))
                if d["uri"] != g["uri"]:
                    groups.append((d["img"], [{"deleteContentRange": {"range": rng(d["img"], d["img"] + 1)}},
                                              {"insertInlineImage": {"uri": g["uri"], "location": {"index": d["img"]},
                                                                     "objectSize": fig_size(g["fkey"])}}]))
        delete_units([olds[i] for i in range(len(olds)) if i not in used])
        # new units: insert after the nearest preceding unit that exists in the doc
        run = []
        for gi, g in enumerate(news):
            if gi in paired_new:
                if run:
                    anchor = olds[paired_new[gi] - 1] if paired_new[gi] > 0 else du[i1 - 1]
                    insert_after(anchor["end"] if anchor["type"] != "T" else anchor["cap_end"], run)
                    run = []
                continue
            run.append(g)
        if run:
            prev = [olds[b] for b, g2 in pairs if g2 < j2 - j1]
            anchor = olds[max(b for b, _ in pairs)] if pairs else du[i1 - 1]
            if anchor["type"] == "T":
                sys.exit("inserting after a table is not handled; anchor on a paragraph")
            insert_after(anchor["end"], run)

    haystack = full + "".join(inserted_text)
    for a, b in pending_rewords:
        for old, new in minimal_spans(a, b, haystack):
            repl.append({"replaceAllText": {"containsText": {"text": old, "matchCase": True}, "replaceText": new}})
            notes.append(f"reword: {old[:50]!r} -> {new[:50]!r}")
    groups.sort(key=lambda x: -x[0])
    starts = [g[0] for g in groups]
    if len(set(starts)) != len(starts):
        notes.append(f"WARNING: several edits at one index: {sorted(s for s in starts if starts.count(s) > 1)}")
    print("\n".join(notes), file=sys.stderr)
    n = int(os.environ.get("PATCH_CHUNKS", 1))
    if n > 1:
        # split into n batches, bottom-up, never inside a group; the rewords go last. Positions stay valid
        # because each batch only touches indexes above those of the next; read again between batches.
        size = sum(len(json.dumps(rs)) for _, rs in groups) + len(json.dumps(repl))
        chunks, cur, acc = [], [], 0
        for _, rs in groups:
            cur += rs
            acc += len(json.dumps(rs))
            if acc > size / n and len(chunks) < n - 1:
                chunks.append(cur)
                cur, acc = [], 0
        chunks.append(cur + repl)
        return [{"requests": c, "writeControl": {"requiredRevisionId": rev}} for c in chunks]
    req = [r for _, rs in groups for r in rs] + repl
    return {"requests": req, "writeControl": {"requiredRevisionId": rev}}


# ---------------------------------------------------------------- step 2: styles
PFIELDS = ("namedStyleType", "alignment", "spaceAbove", "spaceBelow", "indentFirstLine", "indentStart", "indentEnd",
           "keepWithNext")


def norm_para(st):
    out = {}
    for f in PFIELDS:
        v = st.get(f)
        if f == "alignment":
            v = v or "START"
        elif f == "keepWithNext":
            v = bool(v)
        elif f != "namedStyleType":
            v = round((v or {}).get("magnitude", 0), 2)
        out[f] = v
    return out


def target_para(kind):
    t = nb.para_style(kind)
    return {f: (round(t[f]["magnitude"], 2) if isinstance(t[f], dict) else t[f]) for f in PFIELDS}


def char_targets(b):
    """Expected (bold, italic, highlighted, link, size) for each UTF-16 unit of a block's text."""
    base = nb.TEXT.get(b["kind"], {})
    size = base.get("fontSize", nb.pt(10))["magnitude"]
    plain = b["plain"]
    flags = []
    for ch in plain:
        flags += [dict(b=bool(base.get("bold")), i=bool(base.get("italic")) or b["kind"] == "quote", hl=False, a=None,
                       size=size)] * u16(ch)
    for s, z, tag, href in b["spans"]:
        a0, z0 = u16(plain[:s]), u16(plain[:z])
        for k in range(a0, z0):
            if tag == "b":
                flags[k] = dict(flags[k], b=True)
            elif tag == "i":
                flags[k] = dict(flags[k], i=True)
            elif tag == "hl":
                flags[k] = dict(flags[k], hl=True)
            else:
                flags[k] = dict(flags[k], a=href)
    if b["kind"] in ("abstract", "index"):
        dash = u16(plain[:plain.index("—") + 1])
        for k in range(dash):
            flags[k] = dict(flags[k], b=True, i=True)
    return flags


def doc_chars(par, named_sizes):
    out = []
    for e in par["elements"]:
        if "textRun" not in e:
            continue
        c = e["textRun"]["content"]
        ts = e["textRun"].get("textStyle", {})
        n = u16(c.rstrip("\n"))
        size = ts.get("fontSize", {}).get("magnitude") or named_sizes
        out += [dict(b=bool(ts.get("bold")), i=bool(ts.get("italic")), hl=bool(ts.get("backgroundColor")),
                     a=ts.get("link", {}).get("url"), size=size,
                     font=ts.get("weightedFontFamily", {}).get("fontFamily"))] * n
    return out


def style(doc):
    rev = doc["revisionId"]
    body = doc["tabs"][0]["documentTab"]["body"]["content"]
    named = {s["namedStyleType"]: s for s in doc["tabs"][0]["documentTab"].get("namedStyles", {}).get("styles", [])}
    paras = [el for el in body if "paragraph" in el and (ptext(el["paragraph"]).strip())]
    blocks = [b for b in nb.B]
    if len(paras) != len(blocks):
        sys.exit(f"{len(paras)} paragraphs in the doc, {len(blocks)} blocks in the generator: run content first")
    req, notes = [], []
    for el, b in zip(paras, blocks):
        txt = ptext(el["paragraph"]).rstrip("\n")
        want_txt = "￼" if b["kind"] == "fig" else b["plain"]
        if txt != want_txt:
            sys.exit(f"text differs: {txt[:60]!r} vs {want_txt[:60]!r}")
        a, z = el["startIndex"], el["endIndex"]
        cur = norm_para(el["paragraph"]["paragraphStyle"])
        want = target_para(b["kind"])
        restyled = cur != want
        if cur != want:
            last = req[-1]["updateParagraphStyle"] if req and "updateParagraphStyle" in req[-1] else None
            if last is not None and last["range"]["endIndex"] == a and last.get("_kind") == b["kind"]:
                last["range"]["endIndex"] = z          # merge with the previous paragraph of the same kind
            else:
                st = dict(nb.para_style(b["kind"]), lineSpacing=100)
                req.append({"updateParagraphStyle": {"range": rng(a, z), "paragraphStyle": st, "fields": ",".join(st),
                                                     "_kind": b["kind"]}})
            notes.append(f"paragraph style {b['kind']}: {[f for f in PFIELDS if cur[f] != want[f]]} :: {txt[:40]!r}")
        if b["kind"] == "fig":
            continue
        ns = named.get(el["paragraph"]["paragraphStyle"].get("namedStyleType"), {})
        nsize = ns.get("textStyle", {}).get("fontSize", {}).get("magnitude", 11)
        have, want_c = doc_chars(el["paragraph"], nsize), char_targets(b)
        bad = len(have) != len(want_c) or any(h["font"] != "Times New Roman" for h in have) or any(
            (h["b"], h["i"], h["hl"], h["a"], h["size"]) != (w["b"], w["i"], w["hl"], w["a"], w["size"])
            for h, w in zip(have, want_c))
        if bad or restyled:     # setting namedStyleType clears the text style, so always reapply it
            base = dict(weightedFontFamily=nb.FONT, fontSize=nb.pt(want_c[0]["size"] if want_c else 10),
                        bold=bool(nb.TEXT.get(b["kind"], {}).get("bold")),
                        italic=bool(nb.TEXT.get(b["kind"], {}).get("italic")) or b["kind"] == "quote",
                        smallCaps=bool(nb.TEXT.get(b["kind"], {}).get("smallCaps")))
            req.append({"updateTextStyle": {"range": rng(a, z - 1), "textStyle": base,
                                            "fields": ",".join(base) + ",backgroundColor,link"}})
            for s, e2, tag, href in b["spans"]:
                r_ = rng(a + u16(b["plain"][:s]), a + u16(b["plain"][:e2]))
                st, f = {"b": ({"bold": True}, "bold"), "i": ({"italic": True}, "italic"),
                         "hl": ({"backgroundColor": nb.YELLOW}, "backgroundColor")}.get(tag, ({"link": {"url": href}}, "link"))
                req.append({"updateTextStyle": {"range": r_, "textStyle": st, "fields": f}})
            if b["kind"] in ("abstract", "index"):
                dash = u16(b["plain"][:b["plain"].index("—") + 1])
                req.append({"updateTextStyle": {"range": rng(a, a + dash), "textStyle": {"bold": True, "italic": True},
                                                "fields": "bold,italic"}})
            notes.append(f"text style {b['kind']} :: {txt[:40]!r}")
    for r in req:
        r.get("updateParagraphStyle", {}).pop("_kind", None)
    print("\n".join(notes) or "no style changes", file=sys.stderr)
    return {"requests": req, "writeControl": {"requiredRevisionId": rev}}


def check(doc):
    du, gu = doc_units(doc), gen_units()
    bad = 0
    sm = difflib.SequenceMatcher(a=[u["key"] for u in du], b=[u["key"] for u in gu], autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag != "equal":
            bad += 1
            print(tag, [u["key"][:50] for u in du[i1:i2]], "->", [u["key"][:50] for u in gu[j1:j2]])
        else:
            for d, g in zip(du[i1:i2], gu[j1:j2]):
                if d["type"] in "TF" and d["cap"] != g["cap"]:
                    bad += 1
                    print("caption", d["cap"][:40], "->", g["cap"][:40])
                if d["type"] == "T" and d["rows"] != g["rows"]:
                    bad += 1
                    print("table rows differ:", g["tkey"])
                if d["type"] == "F" and d["uri"] != g["uri"]:
                    bad += 1
                    print("figure differs:", g["fkey"])
    print(f"{len(du)} units in the doc, {len(gu)} in the generator, {bad} differences")


if __name__ == "__main__":
    cmd, path = sys.argv[1], sys.argv[2]
    d = load_doc(path)
    if cmd == "check":
        check(d)
    else:
        out = content(d) if cmd == "content" else style(d)
        if isinstance(out, list):                  # PATCH_CHUNKS > 1: one file per batch in $OUT
            for k, o in enumerate(out):
                path = os.path.join(os.environ.get("OUT", "."), f"patch_{k}.json")
                json.dump(o, open(path, "w"), ensure_ascii=False, separators=(",", ":"))
                print(path, len(o["requests"]), "requests", os.path.getsize(path), "bytes", file=sys.stderr)
        else:
            json.dump(out, sys.stdout, ensure_ascii=False, separators=(",", ":"))
