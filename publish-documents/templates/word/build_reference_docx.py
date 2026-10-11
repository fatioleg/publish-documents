#!/usr/bin/env python3
"""Gera os reference docs do perfil word-editable a partir do reference.docx padrão do Pandoc.

Estilos:
  tecnico  (padrão) relatório técnico/científico: Cambria 11, entrelinha 1,15, títulos em azul-marinho
           com filete sob o nível 1, tabelas em estilo booktabs com cabeçalho em negrito, citações
           (`>`) como quadro sombreado com barra lateral. Portado do pipeline ref_rck do autor
           (pandoc --reference-doc=ref_rck.docx), que é a régua de qualidade deste perfil.
  abnt     inspirado na ABNT NBR 14724: A4; margens 3/2 cm; Times 12; entrelinha 1,5; recuo de 1,25 cm
           só no corpo (nunca em células de tabela); seções primárias em caixa alta; `>` = citação longa
           (recuo de 4 cm, corpo 10).

Rodar só para regenerar os binários versionados (requer python-docx):

    quarto pandoc -o /tmp/base.docx --print-default-data-file reference.docx
    python build_reference_docx.py /tmp/base.docx reference-tecnico.docx --style tecnico
    python build_reference_docx.py /tmp/base.docx reference-abnt.docx --style abnt
"""

import argparse

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

NAVY = RGBColor(0x1F, 0x3A, 0x5F)
GREY = RGBColor(0x44, 0x44, 0x44)
BLACK = RGBColor(0, 0, 0)
JUSTIFY, CENTER, LEFT = WD_ALIGN_PARAGRAPH.JUSTIFY, WD_ALIGN_PARAGRAPH.CENTER, WD_ALIGN_PARAGRAPH.LEFT


def style(doc, name, kind=WD_STYLE_TYPE.PARAGRAPH):
    try:
        return doc.styles[name]
    except KeyError:
        return doc.styles.add_style(name, kind)


def fmt(st, font, size=None, bold=None, italic=None, caps=None, color=None, spacing=None, before=None,
        after=None, indent=None, left=None, align=None):
    st.font.name = font
    rpr = st.element.get_or_add_rPr()
    fonts = rpr.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        rpr.append(fonts)
    for attr in ("ascii", "hAnsi", "cs", "eastAsia"):
        fonts.set(qn(f"w:{attr}"), font)
    for attr in ("asciiTheme", "hAnsiTheme", "cstheme", "eastAsiaTheme"):
        fonts.attrib.pop(qn(f"w:{attr}"), None)
    for key, value in (("size", Pt(size) if size else None), ("bold", bold), ("italic", italic), ("all_caps", caps)):
        if value is not None:
            setattr(st.font, key, value)
    if color is not None:
        st.font.color.rgb = color
    pf = st.paragraph_format
    if spacing is not None:
        pf.line_spacing = spacing
    if before is not None:
        pf.space_before = Pt(before)
    if after is not None:
        pf.space_after = Pt(after)
    if indent is not None:
        pf.first_line_indent = indent
    if left is not None:
        pf.left_indent = left
    if align is not None:
        pf.alignment = align


# ordem dos filhos exigida pelo schema OOXML (CT_PPr, CT_TblPr); o Word pode ignorar o que vier fora de ordem
PPR_ORDER = ["pStyle", "keepNext", "keepLines", "pageBreakBefore", "framePr", "widowControl", "numPr",
             "suppressLineNumbers", "pBdr", "shd", "tabs", "suppressAutoHyphens", "kinsoku", "wordWrap",
             "overflowPunct", "topLinePunct", "autoSpaceDE", "autoSpaceDN", "bidi", "adjustRightInd", "snapToGrid",
             "spacing", "ind", "contextualSpacing", "mirrorIndents", "suppressOverlap", "jc", "textDirection",
             "textAlignment", "textboxTightWrap", "outlineLvl", "divId", "cnfStyle", "rPr", "sectPr", "pPrChange"]
TBLPR_ORDER = ["tblStyle", "tblpPr", "tblOverlap", "bidiVisual", "tblStyleRowBandSize", "tblStyleColBandSize", "tblW",
               "jc", "tblCellSpacing", "tblInd", "tblBorders", "shd", "tblLayout", "tblCellMar", "tblLook",
               "tblCaption", "tblDescription", "tblPrChange"]


def put_in_order(parent, element, order):
    """Substitui o filho de mesmo nome e insere `element` na posição do schema."""
    name = element.tag.split("}")[1]
    for old in parent.findall(qn(f"w:{name}")):
        parent.remove(old)
    later = {qn(f"w:{n}") for n in order[order.index(name) + 1:]}
    for idx, child in enumerate(parent):
        if child.tag in later:
            parent.insert(idx, element)
            return
    parent.append(element)


def replace_ppr(st, tag, element):
    put_in_order(st.element.get_or_add_pPr(), element, PPR_ORDER)


def border(tag, **attrs):
    el = OxmlElement(tag)
    for k, v in attrs.items():
        el.set(qn(f"w:{k}"), v)
    return el


def table_style(doc, rule_color, inner_color):
    """Estilo `Table` do Pandoc: filetes superior/inferior, divisórias horizontais claras, cabeçalho em negrito."""
    st = style(doc, "Table", WD_STYLE_TYPE.TABLE)
    tpr = st.element.find(qn("w:tblPr"))
    if tpr is None:
        tpr = OxmlElement("w:tblPr")
        st.element.append(tpr)
    borders = OxmlElement("w:tblBorders")
    for side, size, color in (("top", "12", rule_color), ("bottom", "12", rule_color), ("insideH", "4", inner_color)):
        borders.append(border(f"w:{side}", val="single", sz=size, space="0", color=color))
    put_in_order(tpr, borders, TBLPR_ORDER)
    for old in st.element.findall(qn("w:tblStylePr")):
        if old.get(qn("w:type")) == "firstRow":
            st.element.remove(old)
    first = OxmlElement("w:tblStylePr")
    first.set(qn("w:type"), "firstRow")
    rpr = OxmlElement("w:rPr")
    rpr.append(OxmlElement("w:b"))
    first.append(rpr)
    tcpr = OxmlElement("w:tcPr")
    tcb = OxmlElement("w:tcBorders")
    tcb.append(border("w:bottom", val="single", sz="8", space="0", color=rule_color))
    tcpr.append(tcb)
    first.append(tcpr)
    st.element.append(first)


def build_tecnico(doc):
    font = "Cambria"
    for section in doc.sections:
        section.page_width, section.page_height = Cm(21), Cm(29.7)
        section.left_margin = section.right_margin = Cm(2.3)
        section.top_margin = section.bottom_margin = Cm(2.2)
    for name in ("Normal", "Body Text", "First Paragraph"):
        fmt(style(doc, name), font, 11, spacing=1.15, after=6, indent=Cm(0), align=JUSTIFY)
    fmt(style(doc, "Compact"), font, 10.5, spacing=1.0, before=1, after=1, indent=Cm(0), align=LEFT)
    fmt(style(doc, "Title"), font, 22, bold=True, color=NAVY, align=CENTER, after=6)
    fmt(style(doc, "Subtitle"), font, 14, bold=False, italic=True, color=GREY, align=CENTER, after=6)
    fmt(style(doc, "Author"), font, 11, italic=True, color=GREY, align=CENTER)
    fmt(style(doc, "Date"), font, 10, italic=True, color=GREY, align=CENTER, after=12)
    fmt(style(doc, "Abstract"), font, 10.5, spacing=1.15, before=6, after=6, align=JUSTIFY)
    for name, size, before in (("Heading 1", 15, 14), ("Heading 2", 12.5, 10), ("Heading 3", 11.5, 10),
                               ("Heading 4", 11, 8), ("Heading 5", 11, 8)):
        fmt(style(doc, name), font, size, bold=True, italic=False, caps=False, color=NAVY, before=before,
            after=4, indent=Cm(0), align=LEFT)
    rule = OxmlElement("w:pBdr")
    rule.append(border("w:bottom", val="single", sz="6", space="2", color="1F3A5F"))
    replace_ppr(style(doc, "Heading 1"), "w:pBdr", rule)
    block = style(doc, "Block Text")
    fmt(block, font, 10.5, italic=False, color=RGBColor(0x22, 0x22, 0x22), spacing=1.1, before=4, after=6,
        indent=Cm(0), align=JUSTIFY)
    bar = OxmlElement("w:pBdr")
    bar.append(border("w:left", val="single", sz="24", space="8", color="1F3A5F"))
    replace_ppr(block, "w:pBdr", bar)
    replace_ppr(block, "w:shd", border("w:shd", val="clear", color="auto", fill="EEF2F7"))
    replace_ppr(block, "w:ind", border("w:ind", left="360", right="360", firstLine="0"))
    for name in ("Caption", "Image Caption", "Table Caption"):
        fmt(style(doc, name), font, 9.5, italic=True, color=GREY, spacing=1.0, before=4, after=8, indent=Cm(0),
            align=LEFT)
    fmt(style(doc, "Footnote Text"), font, 9, spacing=1.0, align=JUSTIFY)
    fmt(style(doc, "Bibliography"), font, 10, spacing=1.0, after=6, indent=Cm(0), align=LEFT)
    fmt(style(doc, "TOC Heading"), font, 15, bold=True, color=NAVY, align=LEFT, after=6)
    table_style(doc, "1F3A5F", "BFC8D6")


def build_abnt(doc):
    font = "Times New Roman"
    for section in doc.sections:
        section.page_width, section.page_height = Cm(21), Cm(29.7)
        section.top_margin, section.left_margin = Cm(3), Cm(3)
        section.bottom_margin, section.right_margin = Cm(2), Cm(2)
    fmt(style(doc, "Normal"), font, 12, color=BLACK, spacing=1.5, before=0, after=0, indent=Cm(0), align=JUSTIFY)
    for name in ("Body Text", "First Paragraph"):
        fmt(style(doc, name), font, 12, spacing=1.5, before=0, after=0, indent=Cm(1.25), align=JUSTIFY)
    # células de tabela usam Compact, que herda de Body Text: zerar o recuo e a justificação
    fmt(style(doc, "Compact"), font, 10, spacing=1.0, before=0, after=0, indent=Cm(0), left=Cm(0), align=LEFT)
    fmt(style(doc, "Title"), font, 14, bold=True, caps=True, color=BLACK, align=CENTER, after=12)
    fmt(style(doc, "Subtitle"), font, 12, bold=False, italic=False, caps=False, color=BLACK, align=CENTER, after=12)
    for name in ("Author", "Date"):
        fmt(style(doc, name), font, 12, italic=False, caps=False, color=BLACK, align=CENTER)
    fmt(style(doc, "Abstract"), font, 12, spacing=1.0, before=6, after=6, indent=Cm(0), align=JUSTIFY)
    fmt(style(doc, "Heading 1"), font, 12, bold=True, caps=True, color=BLACK, before=18, after=12, indent=Cm(0),
        align=LEFT)
    fmt(style(doc, "Heading 2"), font, 12, bold=True, caps=False, color=BLACK, before=12, after=12, indent=Cm(0),
        align=LEFT)
    fmt(style(doc, "Heading 3"), font, 12, bold=True, italic=True, color=BLACK, before=12, after=6, indent=Cm(0),
        align=LEFT)
    for name in ("Heading 4", "Heading 5"):
        fmt(style(doc, name), font, 12, bold=False, italic=True, color=BLACK, before=12, after=6, indent=Cm(0),
            align=LEFT)
    for name in ("Caption", "Image Caption", "Table Caption"):
        fmt(style(doc, name), font, 10, italic=False, color=BLACK, spacing=1.0, before=6, after=6, indent=Cm(0),
            align=CENTER)
    fmt(style(doc, "Footnote Text"), font, 10, spacing=1.0, align=JUSTIFY)
    fmt(style(doc, "Block Text"), font, 10, spacing=1.0, before=6, after=6, indent=Cm(0), left=Cm(4), align=JUSTIFY)
    fmt(style(doc, "Bibliography"), font, 12, spacing=1.0, after=12, indent=Cm(0), align=LEFT)
    fmt(style(doc, "TOC Heading"), font, 12, bold=True, caps=True, color=BLACK, align=CENTER, after=12)
    table_style(doc, "000000", "BFBFBF")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--style", choices=("tecnico", "abnt"), default="tecnico")
    args = ap.parse_args()
    doc = Document(args.src)
    (build_tecnico if args.style == "tecnico" else build_abnt)(doc)
    doc.save(args.dst)


if __name__ == "__main__":
    main()
