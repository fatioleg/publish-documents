// UAH report-visual — template Typst para relatórios científicos, técnicos e propostas.
// Aceita todos os argumentos do typst-show.typ do Quarto + institution, report-number,
// accent, cover e confidential. Fontes com fallback para as embutidas no Typst.

#let article(
  title: none,
  subtitle: none,
  authors: none,
  keywords: (),
  date: none,
  abstract-title: none,
  abstract: none,
  thanks: none,
  cols: 1,
  lang: "pt",
  region: "BR",
  font: none,
  fontsize: 11pt,
  title-size: 2.1em,
  subtitle-size: 1.25em,
  heading-family: none,
  heading-weight: "bold",
  heading-style: "normal",
  heading-color: none,
  heading-line-height: 0.65em,
  mathfont: none,
  codefont: none,
  linestretch: 1.15,
  sectionnumbering: "1.1",
  linkcolor: none,
  citecolor: none,
  filecolor: none,
  toc: false,
  toc_title: none,
  toc_depth: none,
  toc_indent: 1.5em,
  institution: none,
  report-number: none,
  accent: rgb("#1f4e79"),
  cover: true,
  confidential: none,
  biblio-title: [Referências],
  doc,
) = {
  let body-font = if font != none { font } else { ("Libertinus Serif", "New Computer Modern") }
  let head-font = if heading-family != none { heading-family } else { ("Inter", "Libertinus Serif") }
  let head-color = if heading-color != none { heading-color } else { accent }
  let muted = luma(90)

  set document(title: title, keywords: keywords)
  set document(
    author: authors.map(author => content-to-string(author.name)).join(", ", last: " & "),
  ) if authors != none and authors != ()

  set text(lang: lang, region: region, size: fontsize, font: body-font)
  set par(justify: true, leading: linestretch * 0.65em, spacing: 1.1em)
  show math.equation: set text(font: mathfont) if mathfont != none
  show raw: set text(font: codefont) if codefont != none
  show link: set text(fill: rgb(content-to-string(linkcolor))) if linkcolor != none
  show ref: set text(fill: rgb(content-to-string(citecolor))) if citecolor != none

  // Títulos: numerados, cor de destaque, nível 1 com filete.
  set heading(numbering: sectionnumbering)
  show heading: set text(font: head-font, fill: head-color, weight: heading-weight)
  show heading.where(level: 1): it => {
    v(1.2em, weak: true)
    block(below: 0.9em, {
      set text(size: 1.35em)
      it
      v(-0.45em)
      line(length: 100%, stroke: 0.6pt + accent.lighten(40%))
    })
  }
  show heading.where(level: 2): set text(size: 1.12em)
  show heading.where(level: 3): set text(size: 1em, style: "italic")

  // Figuras e tabelas: legendas discretas, rótulo em destaque.
  show figure.caption: it => {
    set text(size: 0.88em, fill: muted)
    set par(justify: false)
    [#text(weight: "bold", fill: accent)[#it.supplement #context it.counter.display(it.numbering)]#it.separator#it.body]
  }
  show figure.where(kind: table): set figure.caption(position: top)
  set table(inset: (x: 6pt, y: 5pt), stroke: none)
  show table: it => {
    set text(size: 0.92em)
    block(stroke: (top: 1pt + black, bottom: 1pt + black), it)
  }
  show table.cell.where(y: 0): set text(weight: "bold")

  // Bibliografia (Typst nativo): título configurável, sem numeração.
  set bibliography(title: biblio-title)
  show bibliography: set heading(numbering: none)

  // Página: A4. Com capa: cabeçalho/rodapé em todas as páginas após a capa
  // (a capa desliga os seus). Sem capa: a partir da 2ª página.
  let show-chrome() = cover or counter(page).get().first() > 1
  set page(
    paper: "a4",
    margin: (top: 2.6cm, bottom: 2.4cm, x: 2.4cm),
    header: context {
      if show-chrome() {
        set text(size: 0.8em, fill: muted, font: head-font)
        grid(columns: (1fr, auto),
          if title != none { title } else { [] },
          if report-number != none { report-number } else { [] })
        v(-0.6em)
        line(length: 100%, stroke: 0.4pt + luma(200))
      }
    },
    footer: context {
      if show-chrome() {
        set text(size: 0.8em, fill: muted, font: head-font)
        grid(columns: (1fr, auto),
          if confidential != none { text(fill: accent)[#confidential] } else if institution != none { institution } else { [] },
          [#counter(page).display() / #counter(page).final().first()])
      }
    },
  )

  // Capa.
  if cover and title != none {
    page(margin: 0pt, header: none, footer: none, {
      block(width: 100%, height: 38%, fill: accent, inset: (x: 2.4cm, top: 3cm, bottom: 1.6cm), {
        set text(fill: white, font: head-font)
        if institution != none { text(size: 0.95em, weight: "medium", upper(institution)) }
        v(1fr)
        text(size: title-size, weight: "bold", title)
        if subtitle != none {
          v(0.5em)
          text(size: subtitle-size, weight: "regular", subtitle)
        }
      })
      block(inset: (x: 2.4cm, y: 1.4cm), width: 100%, {
        set text(font: head-font)
        if authors != none and authors != () {
          for author in authors {
            text(weight: "semibold", author.name)
            if author.affiliation != [] { linebreak(); text(fill: muted, size: 0.9em, author.affiliation) }
            if author.email != [] { linebreak(); text(fill: muted, size: 0.85em, author.email) }
            v(0.9em)
          }
        }
        v(1fr)
      })
      place(bottom + left, dx: 2.4cm, dy: -2cm, {
        set text(font: head-font, size: 0.9em, fill: muted)
        grid(columns: (auto, auto), column-gutter: 2.5em,
          if date != none { date } else { [] },
          if report-number != none { report-number } else { [] })
        if confidential != none { v(0.6em); text(fill: accent, weight: "bold", confidential) }
      })
    })
    counter(page).update(1)
  } else if title != none {
    align(center, block(inset: (bottom: 1.5em), {
      set text(font: head-font)
      text(size: title-size * 0.8, weight: "bold", fill: accent, title)
      if subtitle != none { linebreak(); text(size: subtitle-size, subtitle) }
      if authors != none and authors != () {
        v(0.6em)
        authors.map(a => a.name).join(", ")
      }
      if date != none { linebreak(); text(fill: muted, size: 0.9em, date) }
    }))
  }

  if abstract != none {
    block(fill: accent.lighten(92%), inset: 1.1em, radius: 2pt, width: 100%, below: 1.6em, {
      text(font: head-font, weight: "bold", fill: accent, if abstract-title != none { abstract-title } else { [Resumo] })
      v(0.3em)
      abstract
      if keywords != () {
        v(0.4em)
        text(size: 0.9em, fill: muted)[*Palavras-chave:* #keywords.join("; ")]
      }
    })
  }

  if toc {
    block(below: 2em, {
      set text(font: head-font)
      show outline.entry.where(level: 1): set text(weight: "bold")
      outline(title: if toc_title == none { auto } else { toc_title }, depth: toc_depth, indent: toc_indent)
    })
    pagebreak(weak: true)
  }

  doc
}
