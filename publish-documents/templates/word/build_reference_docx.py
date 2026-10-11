#!/usr/bin/env python3
"""Gera templates/word/reference-abnt.docx a partir do reference.docx padrão do Pandoc.

Formatação inspirada na ABNT NBR 14724 (trabalhos acadêmicos): A4; margens 3 cm (sup./esq.)
e 2 cm (inf./dir.); Times New Roman 12; entrelinha 1,5; recuo de 1,25 cm na primeira linha;
legendas, notas e referências em corpo menor e entrelinha simples; seções primárias em
negrito e caixa alta. Rodar só para regenerar o arquivo binário versionado:

    quarto pandoc -o /tmp/base.docx --print-default-data-file reference.docx
    python build_reference_docx.py /tmp/base.docx reference-abnt.docx      (requer python-docx)
"""

import sys

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.shared import Cm, Pt, RGBColor

FONT = "Times New Roman"
BLACK = RGBColor(0, 0, 0)


def style(doc, name):
    try:
        return doc.styles[name]
    except KeyError:
        return doc.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)


def fmt(st, size=12, bold=None, italic=None, caps=None, spacing=1.5, before=0, after=0,
        indent=None, align=None):
    st.font.name = FONT
    st.font.size = Pt(size)
    st.font.color.rgb = BLACK
    if bold is not None:
        st.font.bold = bold
    if italic is not None:
        st.font.italic = italic
    if caps is not None:
        st.font.all_caps = caps
    rpr = st.element.get_or_add_rPr()
    fonts = rpr.find("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rFonts")
    if fonts is not None:
        for attr in ("ascii", "hAnsi", "cs", "eastAsia"):
            fonts.set(f"{{http://schemas.openxmlformats.org/wordprocessingml/2006/main}}{attr}", FONT)
        for attr in ("asciiTheme", "hAnsiTheme", "cstheme", "eastAsiaTheme"):
            fonts.attrib.pop(f"{{http://schemas.openxmlformats.org/wordprocessingml/2006/main}}{attr}", None)
    pf = st.paragraph_format
    pf.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE if spacing == 1.5 else WD_LINE_SPACING.SINGLE
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)
    if indent is not None:
        pf.first_line_indent = indent
    if align is not None:
        pf.alignment = align


def main(src: str, dst: str) -> None:
    doc = Document(src)
    for section in doc.sections:
        section.page_width, section.page_height = Cm(21), Cm(29.7)
        section.top_margin, section.left_margin = Cm(3), Cm(3)
        section.bottom_margin, section.right_margin = Cm(2), Cm(2)

    justify, center, left = WD_ALIGN_PARAGRAPH.JUSTIFY, WD_ALIGN_PARAGRAPH.CENTER, WD_ALIGN_PARAGRAPH.LEFT
    fmt(style(doc, "Normal"), align=justify)
    for name in ("Body Text", "First Paragraph"):
        fmt(style(doc, name), indent=Cm(1.25), align=justify)
    fmt(style(doc, "Compact"), spacing=1, align=left)
    fmt(style(doc, "Title"), size=14, bold=True, caps=True, align=center, after=12)
    fmt(style(doc, "Subtitle"), size=12, caps=False, bold=False, align=center, after=12)
    for name in ("Author", "Date"):
        fmt(style(doc, name), caps=False, bold=False, align=center)
    fmt(style(doc, "Abstract"), spacing=1, align=justify, before=6, after=6)
    fmt(style(doc, "Heading 1"), bold=True, caps=True, before=18, after=12, indent=Cm(0), align=left)
    fmt(style(doc, "Heading 2"), bold=True, caps=False, before=12, after=12, indent=Cm(0), align=left)
    fmt(style(doc, "Heading 3"), bold=True, italic=True, before=12, after=6, indent=Cm(0), align=left)
    for name in ("Heading 4", "Heading 5"):
        fmt(style(doc, name), italic=True, before=12, after=6, indent=Cm(0), align=left)
    for name in ("Caption", "Image Caption", "Table Caption"):
        fmt(style(doc, name), size=10, italic=False, spacing=1, before=6, after=6, indent=Cm(0), align=center)
    fmt(style(doc, "Footnote Text"), size=10, spacing=1, align=justify)
    fmt(style(doc, "Block Text"), size=10, spacing=1, indent=Cm(0), align=justify)
    style(doc, "Block Text").paragraph_format.left_indent = Cm(4)  # citação longa: recuo de 4 cm
    fmt(style(doc, "Bibliography"), spacing=1, after=12, indent=Cm(0), align=left)
    fmt(style(doc, "TOC Heading"), bold=True, caps=True, align=center, after=12)
    doc.save(dst)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
