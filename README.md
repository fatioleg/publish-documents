# publish-documents

> **Protocolo editorial, não um sistema editorial.** Uma skill do [Claude Code](https://claude.com/claude-code)
> que transforma uma fonte única em [Quarto](https://quarto.org) (`document.qmd`) em PDF e DOCX de padrão
> profissional. O agente escreve o conteúdo; a CLI (Typst, LaTeX ou Word) faz o layout.

Integra o fluxo do [Universal Agent Harness](https://github.com/fatioleg/Universal-Agent-Harness) como a
integração `publish-documents`.

## Perfis

| Perfil | Motor | Para |
|---|---|---|
| `report-visual` | Quarto → Typst → PDF | relatórios científicos, técnicos e institucionais; propostas em PDF |
| `journal-scientific` | Quarto → XeLaTeX → PDF (+ `.tex`) | artigos teóricos, equações, submissão em LaTeX |
| `word-editable` | Quarto/Pandoc → DOCX (estilo `tecnico` ou `abnt`) | relatórios e textos técnicos editáveis, pareceres, editais em Word |

O template `report-visual` traz capa com faixa de cor, índice, cabeçalho e rodapé com numeração `n / total`,
títulos numerados, tabelas em estilo editorial, legendas discretas e resumo destacado. Todas as fontes vão
embutidas, com fallback para as fontes do próprio Typst.

O DOCX tem dois estilos (`new --docx-style`):

- `tecnico` (padrão): Cambria 11, entrelinha 1,15, títulos em azul-marinho com filete sob o nível 1, tabelas
  em estilo booktabs com cabeçalho em negrito, e citações (`>`) como quadros sombreados com barra lateral,
  bons para analogias e "pare e confira". É o estilo do pipeline `ref_rck` do autor, que é a régua deste perfil.
- `abnt`: A4, margens 3/2 cm, Times 12, entrelinha 1,5, recuo de 1,25 cm só no corpo (nunca nas tabelas),
  títulos primários em caixa alta, `>` como citação longa (recuo de 4 cm, corpo 10) e sumário.

Equações com `\tag{143}` mantêm o número no DOCX, alinhado à direita. O Pandoc sozinho descarta o `\tag`; o
`render` usa um filtro Lua e um pós-processamento, e o `verify` reprova o DOCX se algum número faltar. O
`preflight` reprova títulos já numerados à mão com `number-sections: true`, que geraria numeração dupla.

## Comandos

```bash
P=~/.claude/skills/publish-documents/scripts/pubdoc.py
python3 $P doctor                                    # testa Quarto, Typst, motores TeX, LibreOffice, poppler
python3 $P new publication --profile report-visual --title "Meu relatório" --with-docx
python3 $P preflight publication                     # citações, cross-refs, figuras, alt text, metadados
python3 $P render publication                        # formato principal (edição)
python3 $P render publication --all                  # todos os formatos (entrega)
python3 $P verify publication                        # páginas, fontes, refs não resolvidas, DOCX, prévia, manifesto
```

O `verify` gera `outputs/_review/*-contato.png` (folha de contato para inspeção visual) e
`outputs/manifest.json` com os hashes das fontes e saídas e as versões das ferramentas.

## Instalação

```bash
git clone git@github.com:fatioleg/publish-documents.git ~/.claude/tools/publish-documents
ln -s ~/.claude/tools/publish-documents/publish-documents ~/.claude/skills/publish-documents
```

Requisitos:
- Quarto ≥ 1.6 (traz Pandoc e Typst);
- Python 3 + PyYAML;
- opcionais: XeLaTeX (perfil `journal-scientific`), LibreOffice (prévia de DOCX e SVG→PDF), poppler-utils (verificação de PDF), Pillow (folha de contato), `libreoffice-math` (equações na prévia do DOCX).

Com o UAH: `uah.py integrations install publish-documents`.

## Testes

```bash
python3 -m unittest discover -s tests -v
```

São 15 testes. Os de integração compilam os três perfis de verdade quando o Quarto e o XeLaTeX estão instalados.

## Licença

MIT. Os estilos CSL (ABNT, ACS) são do projeto Citation Style Language, sob CC BY-SA 3.0.
