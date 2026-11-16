"""Patches the live Google Doc from one version of build_doc.py to the next, without a full rebuild.

    python3 docs/paper/patch_doc.py OLD_build_doc.py READ.json > batch.json

OLD_build_doc.py is the generator version the doc currently matches (e.g. `git show HEAD:docs/paper/build_doc.py`),
READ.json a fresh read of the doc. Handles: changed sentences inside a paragraph (replaceAllText), new body
paragraphs after an existing one, new rows at the end of a table, and new blocks appended at the end of the doc
(headings, table captions with their tables). Anything else stops with an error; rebuild the doc in that case.
"""
import difflib
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    m.__file__ = os.path.join(HERE, "build_doc.py")     # so REPO and TABLES resolve
    src = open(path).read()
    exec(compile(src, path, "exec"), m.__dict__)
    m.layout()
    return m


def main():
    old = load(sys.argv[1], "bd_old")
    new = load(os.path.join(HERE, "build_doc.py"), "bd_new")
    doc = json.load(open(sys.argv[2]))
    while isinstance(doc, dict) and "content" in doc and not isinstance(doc.get("content"), list):
        doc = doc["content"]
    rev = doc["revisionId"]
    body = doc["tabs"][0]["documentTab"]["body"]["content"]
    u16 = new.u16

    def ptext(el):
        return "".join(e.get("textRun", {}).get("content", "") for e in el["paragraph"]["elements"])

    paras = [(el["startIndex"], el["endIndex"], ptext(el)) for el in body if "paragraph" in el]
    tables = [el for el in body if "table" in el]
    all_text = json.dumps(doc, ensure_ascii=False)

    def find_para(plain):
        hits = [p for p in paras if p[2].rstrip("\n") == plain]
        if len(hits) != 1:
            sys.exit(f"{len(hits)} paragraphs match {plain[:60]!r}")
        return hits[0]

    ob, nb = [b["plain"] for b in old.B], [b["plain"] for b in new.B]
    end_req, mid_req, table_req, repl_req, notes = [], [], [], [], []
    sm = difflib.SequenceMatcher(a=ob, b=nb, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        if tag == "replace" and i2 - i1 == j2 - j1:
            for a, b in zip(ob[i1:i2], nb[j1:j2]):          # same paragraph, changed wording
                m = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
                blocks = [op for op in m.get_opcodes() if op[0] != "equal"]
                lo, hi = blocks[0][1], blocks[-1][2]
                lo2, hi2 = blocks[0][3], blocks[-1][4]
                while lo > 0 and (a[:hi].count(a[lo:hi]) != 1 or all_text.count(json.dumps(a[lo:hi], ensure_ascii=False)[1:-1]) != 1 or hi - lo < 25):
                    lo -= 1
                    lo2 -= 1
                find_para(a)
                repl_req.append({"replaceAllText": {"containsText": {"text": a[lo:hi], "matchCase": True}, "replaceText": b[lo2:hi2]}})
                notes.append(f"reword: {a[lo:hi][:70]!r} -> {b[lo2:hi2][:70]!r}")
        elif tag == "insert" and i1 == len(ob):               # new blocks at the end of the document
            at = paras[-1][0]
            text = "".join(p + "\n" for p in nb[j1:j2])
            end_req.append({"insertText": {"location": {"index": at}, "text": text}})
            pos = at
            for b in new.B[j1:j2]:
                z = pos + u16(b["plain"]) + 1
                st = new.para_style(b["kind"])
                st.update(lineSpacing=100)
                end_req.append({"updateParagraphStyle": {"range": new.rng(pos, z), "paragraphStyle": st, "fields": ",".join(st)}})
                ts = dict(weightedFontFamily=new.FONT, fontSize=new.pt(10), bold=False, italic=False, smallCaps=False)
                ts.update(new.TEXT.get(b["kind"], {}))
                end_req.append({"updateTextStyle": {"range": new.rng(pos, z), "textStyle": ts, "fields": ",".join(ts)}})
                b["_at"] = (pos, z)
                pos = z
            for b in reversed(new.B[j1:j2]):                   # tables, bottom-up
                if b["kind"] == "tcap":
                    end_req += new.table_requests(b["table"], b["_at"][1] - 1)
                elif b["kind"] == "fig":
                    sys.exit("new figures are not handled; rebuild")
            notes.append(f"append at end: {[b['kind'] for b in new.B[j1:j2]]}")
        elif tag == "insert" and all(b["kind"] == "p" for b in new.B[j1:j2]) and old.B[i1 - 1]["kind"] == "p":
            s, e, _ = find_para(ob[i1 - 1])                    # new body paragraphs after an existing one
            mid_req.append((e - 1, {"insertText": {"location": {"index": e - 1}, "text": "".join("\n" + p for p in nb[j1:j2])}}))
            notes.append(f"insert {j2 - j1} paragraphs after {ob[i1 - 1][:50]!r}")
        else:
            sys.exit(f"cannot patch {tag} old[{i1}:{i2}] new[{j1}:{j2}]; rebuild the doc")

    for key in old.T:                                          # rows added at the end of an existing table
        orow, nrow = old.T[key][1], new.T[key][1]
        if orow == nrow:
            continue
        if nrow[:len(orow)] != orow or key not in old.TN:
            sys.exit(f"table {key} changed in a way that cannot be patched; rebuild")
        el = tables[old.TN[key] - 1]
        C, R = len(orow[0]), len(orow)
        S, E = el["startIndex"], el["endIndex"] - 1     # the last row ends one index before the table does
        extra = nrow[len(orow):]
        reqs = [{"insertTableRow": {"tableCellLocation": {"tableStartLocation": {"index": S}, "rowIndex": R - 1 + k, "columnIndex": 0},
                                    "insertBelow": True}} for k in range(len(extra))]
        stride = 2 * C + 1
        cells = [(r, c, str(row[c])) for r, row in enumerate(extra) for c in range(C)]
        for r, c, t in reversed(cells):
            if t:
                reqs.append({"insertText": {"location": {"index": E + r * stride + 2 + 2 * c}, "text": t}})
        total = sum(u16(t) for _, _, t in cells)
        z = E + len(extra) * stride + total
        reqs.append({"updateTextStyle": {"range": new.rng(E, z), "textStyle": {"weightedFontFamily": new.FONT, "fontSize": new.pt(8),
                                                                                 "bold": False, "italic": False},
                                         "fields": "weightedFontFamily,fontSize,bold,italic"}})
        reqs.append({"updateParagraphStyle": {"range": new.rng(E, z), "paragraphStyle": {
            "alignment": "START" if key in new.TEXT_HEAVY else "CENTER", "spaceAbove": new.pt(0), "spaceBelow": new.pt(0),
            "indentFirstLine": new.pt(0), "lineSpacing": 100}, "fields": "alignment,spaceAbove,spaceBelow,indentFirstLine,lineSpacing"}})
        table_req.append((S, reqs))
        notes.append(f"table {key}: {len(extra)} rows added")

    ordered = [(10 ** 9, end_req)] + [(i, [r]) for i, r in mid_req] + table_req
    ordered.sort(key=lambda x: -x[0])                          # bottom-up, so earlier indexes stay valid
    req = [r for _, rs in ordered for r in rs] + repl_req
    json.dump({"requests": req, "writeControl": {"requiredRevisionId": rev}}, sys.stdout, ensure_ascii=False, separators=(",", ":"))
    print("\n".join(notes), file=sys.stderr)


if __name__ == "__main__":
    main()
