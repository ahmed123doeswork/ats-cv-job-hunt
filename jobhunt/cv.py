"""Build an ATS-friendly CV (PDF + DOCX) from data/profile.json.

ATS rules followed: one column, standard section headings, real text (no images or tables),
contact details in the body (not a header), plain bullets, consistent dates.
"""
import io
import re
from datetime import datetime
from pathlib import Path

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
FONT_DIR = Path("C:/Windows/Fonts")


def fmt_date(v):
    """'2024-03' -> 'Mar 2024'; '2024' -> '2024'."""
    m = re.match(r"^(\d{4})-(\d{2})", v or "")
    if m:
        return f"{MONTHS[int(m.group(2)) - 1]} {m.group(1)}"
    return (v or "").strip()


def span(item):
    start = fmt_date(item.get("start"))
    end = "Present" if item.get("current") else fmt_date(item.get("end"))
    return " – ".join(p for p in (start, end) if p)


def short_url(u):
    return re.sub(r"^https?://(www\.)?", "", (u or "").strip()).rstrip("/")


def filename(profile, ext):
    name = re.sub(r"[^A-Za-z0-9]+", "_", profile["personal"].get("name") or "My").strip("_") or "My"
    return f"{name}_CV.{ext}"


def sections(p):
    """Profile -> ordered list of (heading, entries). Each entry is a dict with
    left / right / sub / bullets / text. Shared by the PDF and DOCX writers."""
    out = []
    if p.get("summary", "").strip():
        out.append(("Summary", [{"text": p["summary"].strip()}]))
    skills = [g for g in p.get("skills") or [] if g.get("items")]
    if skills:
        out.append(("Skills", [{"text": (f"{g['group']}: " if g.get("group") else "") + ", ".join(g["items"]),
                                "label": g.get("group") or ""} for g in skills]))
    exp = [e for e in p.get("experience") or [] if e.get("title") or e.get("company")]
    if exp:
        out.append(("Experience", [{
            "left": e.get("title", ""), "left2": ", ".join(x for x in (e.get("company"), e.get("location")) if x),
            "right": span(e), "bullets": [b for b in e.get("bullets") or [] if b.strip()]} for e in exp]))
    proj = [x for x in p.get("projects") or [] if x.get("name")]
    if proj:
        out.append(("Projects", [{
            "left": x["name"], "left2": ", ".join(v for v in (x.get("role"), short_url(x.get("link"))) if v),
            "right": span(x), "bullets": [b for b in x.get("bullets") or [] if b.strip()]} for x in proj]))
    edu = [e for e in p.get("education") or [] if e.get("degree") or e.get("school")]
    if edu:
        out.append(("Education", [{
            "left": e.get("degree", ""), "left2": ", ".join(x for x in (e.get("school"), e.get("location")) if x),
            "right": span(e), "bullets": [l for l in (e.get("details") or "").splitlines() if l.strip()]}
            for e in edu]))
    certs = [c for c in p.get("certifications") or [] if c.get("name")]
    if certs:
        out.append(("Certifications", [{
            "left": c["name"], "left2": c.get("issuer", ""), "right": fmt_date(c.get("date"))} for c in certs]))
    awards = [a for a in p.get("awards") or [] if a.get("name")]
    if awards:
        out.append(("Awards and Activities", [{"left": a["name"], "left2": a.get("detail", "")} for a in awards]))
    langs = [l for l in p.get("languages") or [] if l.get("name")]
    if langs:
        out.append(("Languages", [{"text": ", ".join(
            f"{l['name']} ({l['level']})" if l.get("level") else l["name"] for l in langs)}]))
    return out


def contact_line(p):
    me = p["personal"]
    return " | ".join(x for x in (me.get("email"), me.get("phone"), me.get("location"),
                                  short_url(me.get("linkedin")), short_url(me.get("website"))) if x and x.strip())


# ---------------------------------------------------------------- PDF
def pdf_bytes(p):
    from fpdf import FPDF

    pdf = FPDF(format="A4")
    pdf.set_margins(17, 15, 17)
    pdf.set_auto_page_break(True, 15)
    pdf.set_title(f"{p['personal'].get('name', '')} CV")
    fam = "helvetica"
    for name, files in (("Calibri", ("calibri.ttf", "calibrib.ttf", "calibrii.ttf")),
                        ("Arial", ("arial.ttf", "arialbd.ttf", "ariali.ttf"))):
        if all((FONT_DIR / f).is_file() for f in files):
            for style, f in zip(("", "B", "I"), files):
                pdf.add_font(name, style, str(FONT_DIR / f))
            fam = name
            break
    unicode_ok = fam != "helvetica"

    def t(s):
        s = (s or "").replace("\t", " ")
        return s if unicode_ok else s.replace("–", "-").replace("•", "-").encode("latin-1", "replace").decode("latin-1")

    pdf.add_page()
    w = pdf.epw
    base = 10.5 if fam == "Calibri" else 9.8
    lh = base * 0.5

    me = p["personal"]
    pdf.set_font(fam, "B", base * 2.1)
    pdf.cell(w, base * 0.95, t(me.get("name") or "Your Name"), new_x="LMARGIN", new_y="NEXT")
    if me.get("headline"):
        pdf.set_font(fam, "", base * 1.2)
        pdf.cell(w, lh * 1.35, t(me["headline"]), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font(fam, "", base)
    pdf.multi_cell(w, lh, t(contact_line(p)), new_x="LMARGIN", new_y="NEXT")

    for heading, entries in sections(p):
        if pdf.get_y() > pdf.h - 40:
            pdf.add_page()
        pdf.ln(lh * 0.9)
        pdf.set_font(fam, "B", base * 1.1)
        pdf.cell(w, lh * 1.2, t(heading.upper()), new_x="LMARGIN", new_y="NEXT")
        y = pdf.get_y() + 0.4
        pdf.set_draw_color(120, 120, 120)
        pdf.set_line_width(0.25)
        pdf.line(pdf.l_margin, y, pdf.l_margin + w, y)
        pdf.set_y(y + 1.4)
        for e in entries:
            if "text" in e:
                pdf.set_font(fam, "", base)
                label = e.get("label")
                if label:
                    pdf.set_font(fam, "B", base)
                    lw = pdf.get_string_width(t(label + ": "))
                    pdf.cell(lw, lh, t(label + ": "))
                    pdf.set_font(fam, "", base)
                    pdf.multi_cell(w - lw, lh, t(e["text"][len(label) + 2:]), new_x="LMARGIN", new_y="NEXT")
                else:
                    pdf.multi_cell(w, lh, t(e["text"]), new_x="LMARGIN", new_y="NEXT")
                pdf.ln(0.6)
                continue
            right = e.get("right", "")
            pdf.set_font(fam, "", base)
            rw = pdf.get_string_width(t(right)) + 2 if right else 0
            y0 = pdf.get_y()
            pdf.set_font(fam, "B", base)
            pdf.multi_cell(w - rw, lh, t(e["left"]), new_x="LMARGIN", new_y="NEXT")
            y1 = pdf.get_y()
            if right:
                pdf.set_font(fam, "", base)
                pdf.set_xy(pdf.l_margin + w - rw, y0)
                pdf.cell(rw, lh, t(right), align="R")
                pdf.set_xy(pdf.l_margin, y1)
            if e.get("left2"):
                pdf.set_font(fam, "I", base)
                pdf.multi_cell(w, lh, t(e["left2"]), new_x="LMARGIN", new_y="NEXT")
            pdf.set_font(fam, "", base)
            for b in e.get("bullets") or []:
                pdf.set_x(pdf.l_margin + 2)
                pdf.cell(4, lh, t("•"))
                pdf.multi_cell(w - 6, lh, t(b.strip().lstrip("•-* ")), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1.6)
    return bytes(pdf.output())


# ---------------------------------------------------------------- DOCX
def docx_bytes(p):
    from docx import Document
    from docx.enum.text import WD_TAB_ALIGNMENT
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Inches, Pt

    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Inches(8.27), Inches(11.69)
    for side in ("left_margin", "right_margin"):
        setattr(sec, side, Inches(0.7))
    sec.top_margin = sec.bottom_margin = Inches(0.6)
    width = sec.page_width - sec.left_margin - sec.right_margin

    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(10.5)
    normal.paragraph_format.space_after = Pt(0)
    normal.paragraph_format.line_spacing = 1.08

    def para(space_before=0, space_after=0):
        para_ = doc.add_paragraph()
        para_.paragraph_format.space_before = Pt(space_before)
        para_.paragraph_format.space_after = Pt(space_after)
        return para_

    me = p["personal"]
    r = para().add_run(me.get("name") or "Your Name")
    r.bold, r.font.size = True, Pt(22)
    if me.get("headline"):
        para().add_run(me["headline"]).font.size = Pt(12.5)
    para(2).add_run(contact_line(p))

    for heading, entries in sections(p):
        h = para(10, 3)
        hr = h.add_run(heading.upper())
        hr.bold, hr.font.size = True, Pt(11.5)
        pbdr = OxmlElement("w:pBdr")
        bottom = OxmlElement("w:bottom")
        for k, v in (("w:val", "single"), ("w:sz", "6"), ("w:space", "1"), ("w:color", "808080")):
            bottom.set(qn(k), v)
        pbdr.append(bottom)
        h._p.get_or_add_pPr().append(pbdr)
        for e in entries:
            if "text" in e:
                q = para(0, 2)
                if e.get("label"):
                    q.add_run(e["label"] + ": ").bold = True
                    q.add_run(e["text"][len(e["label"]) + 2:])
                else:
                    q.add_run(e["text"])
                continue
            q = para(2)
            q.paragraph_format.tab_stops.add_tab_stop(width, WD_TAB_ALIGNMENT.RIGHT)
            q.add_run(e["left"]).bold = True
            if e.get("right"):
                q.add_run("\t" + e["right"])
            if e.get("left2"):
                para().add_run(e["left2"]).italic = True
            for b in e.get("bullets") or []:
                doc.add_paragraph(b.strip().lstrip("•-* "), style="List Bullet").paragraph_format.space_after = Pt(0)
    buf = io.BytesIO()
    doc.core_properties.title = f"{me.get('name', '')} CV"
    doc.core_properties.created = datetime.now()
    doc.save(buf)
    return buf.getvalue()
