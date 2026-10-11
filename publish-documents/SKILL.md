---
name: publish-documents
description: "Publicação profissional de documentos (PDF e DOCX) a partir de uma fonte única em Quarto (.qmd): relatórios científicos e institucionais com design (Typst), artigos teóricos com equações e template de periódico (LaTeX), documentos editáveis e editais em Word com ABNT. Inclui preflight (citações, referências cruzadas, figuras, texto alternativo), compilação determinística, verificação das saídas (páginas, fontes embutidas, referências não resolvidas), folha de contato para inspeção visual e manifesto de proveniência. Use quando o usuário pedir para gerar, formatar, diagramar ou entregar um relatório, artigo, parecer, proposta ou projeto de fomento em PDF ou Word — mesmo sem dizer Quarto."
---

# publish-documents — protocolo editorial (não um sistema editorial)

O agente escreve **conteúdo semântico** em `document.qmd`. O **layout é da CLI** (Quarto → Typst, LaTeX ou Word).
Não redesenhe páginas por texto e não crie subagentes para tipografia.

CLI: `python3 <skill>/scripts/pubdoc.py`. `<skill>` é a pasta deste arquivo, por exemplo `~/.claude/skills/publish-documents`.

## Escolha do perfil (registre no plano aprovado)

| Perfil | Motor | Quando |
|---|---|---|
| `report-visual` | Quarto → Typst → PDF (capa, índice, cor de destaque) | relatório científico, técnico ou institucional; proposta em PDF livre; relatório de modelagem molecular |
| `journal-scientific` | Quarto → XeLaTeX → PDF (+ `.tex`) | artigo teórico com muitas equações; submissão em LaTeX. **Template oficial da revista tem precedência** |
| `word-editable` | Quarto/Pandoc → DOCX (`reference-abnt.docx`) | parecer, relatório institucional editável, edital que exige Word |

Regras de decisão:
- O template exigido pelo destinatário (revista, agência, edital) **manda**.
- Se o entregável precisa continuar editável, o DOCX é o artefato principal e o PDF é derivado.
- Edital em **plataforma web** (CNPq, FAPEG): entregue texto por seção com contagem de caracteres. Não force DOCX.
- Citações: `abnt` (padrão em pt-BR e documentos institucionais) ou `acs` (química). Para outra revista, baixe a CSL oficial em `csl/`.

## Fluxo

1. **Ambiente (uma vez por máquina):** rode `pubdoc.py doctor`. Ele testa de verdade o Quarto, o Typst, os motores TeX e o LibreOffice. Se um motor falhar, use outro (ex.: o LuaLaTeX quebrado nesta máquina; o XeLaTeX é o padrão).
2. **Estrutura:** `pubdoc.py new publication --profile <perfil> --title "..." [--with-docx] [--csl abnt|acs]`. Isso cria `publication/{document.qmd, references.bib, _quarto.yml, assets/, csl/, templates/, outputs/}`.
3. **Redação:** escreva em `document.qmd`.
   - Citações `[@chave]`; rótulos `{#fig-x}`, `{#tbl-x}`, `{#eq-x}`; referências `@fig-x`.
   - Toda figura leva `fig-alt="..."`.
   - Figuras de dados vêm de dados reais (gráficos via matplotlib / `kd-scientific-visualization`; 3D e perfis via CalcBoard). **Nunca** use ilustração gerada por IA no lugar de resultado. Diagramas conceituais devem ser claramente distinguíveis de dados.
   - Para limite de páginas, use `uah-publish: {page-limit: N}` no YAML.
4. **Preflight (antes de compilar):** `pubdoc.py preflight publication`. Corrija todo `FAIL`. Para validar DOI e metadados das referências, use a skill `kd-citation-management`, o que exige rede e deve ser pedido ao usuário.
5. **Compilar:** durante a edição, só o formato principal: `pubdoc.py render publication`. Na entrega, todos: `pubdoc.py render publication --all`. Figuras SVG são convertidas para PDF no caminho LaTeX (rsvg-convert ou LibreOffice).
6. **Verificar:** `pubdoc.py verify publication`. Ele confere saídas, páginas e limite, fontes embutidas, referências não resolvidas e integridade do DOCX, e gera `outputs/manifest.json`.
7. **Inspeção visual:** abra (Read) `outputs/_review/*-contato.png`.
   - Procure: cortes, páginas vazias, tabelas partidas, equações deslocadas, cabeçalho/rodapé errado, capa.
   - Abra em detalhe só as páginas suspeitas (`*-N.png`).
   - Em entrega crítica, peça revisão humana integral.
   - **Compilar sem erro não significa estar pronto.**
8. **Revisão científica:** conforme o risco, use `kd-peer-review` ou um revisor independente. Confirme que cada afirmação importante tem fonte. Um DOI existente não prova que a fonte sustenta a afirmação.
9. **Aceite:** o responsável aprova. Registre no checkpoint do UAH (ou no specboard): perfil, arquivos finais, avisos restantes e o hash do manifesto.

## Controle de custo

- Gere o alvo principal durante a edição e todos os formatos só na entrega.
- Valide a estrutura (preflight) antes de compilar.
- Na inspeção visual, olhe primeiro a folha de contato e depois só as páginas sinalizadas.
- Uma skill com scripts determinísticos basta: nada de agentes extras para formatar.

## Com o UAH

- Ative a integração com `uah.py integrations enable publish-documents`. Nesse caso:
  - instalar ferramentas (`quarto install`, `quarto add`, `quarto use template`, `tlmgr install`) pede confirmação;
  - antes da aprovação do plano, só o `preflight` roda.
- Documento como fatia: os critérios de aceite são os portões de QA — `AC: preflight sem FAIL`, `AC: verify sem FAIL`, `AC: inspeção visual registrada`, `AC: aceite do responsável`.
- Templates de periódico: extensões oficiais `quarto-journals` (ACS, Elsevier, PLOS…) via `quarto use template quarto-journals/<revista>`. Isso exige rede e confirmação.

## Limites conhecidos

- A prévia do DOCX usa o LibreOffice. Sem `libreoffice-math`, as equações não aparecem na prévia, mas estão no arquivo; o `verify` avisa.
- PDF e DOCX não têm paginação idêntica: valide cada formato.
- A formatação ABNT do `reference-abnt.docx` cobre margens, fonte, entrelinha, recuo, legendas e referências. Capa, folha de rosto e elementos pré-textuais da NBR 14724 ficam por conta do documento.
