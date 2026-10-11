#!/usr/bin/env python3
"""pubdoc — publicação profissional de documentos (PDF/DOCX) com Quarto.

Comandos:
  new        cria publication/ com document.qmd, _quarto.yml, references.bib e templates do perfil
  preflight  verifica a fonte ANTES de compilar (citações, cross-refs, figuras, alt text, metadados)
  render     compila o formato principal do perfil (ou todos com --all) chamando `quarto render`
  doctor     testa de verdade as ferramentas (quarto, typst, motores TeX, LibreOffice, poppler) e diz o que falta
  verify     verifica as saídas (páginas, fontes, refs não resolvidas, DOCX), gera prévia visual
             (outputs/_review/*-contato.png) e grava outputs/manifest.json com hashes e versões

Perfis: report-visual (Typst → PDF), journal-scientific (LuaLaTeX → PDF), word-editable (DOCX).
O layout é sempre da CLI (Quarto/Typst/LaTeX/Word); o agente só escreve o conteúdo em .qmd.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    print("pubdoc precisa de PyYAML: python3 -m pip install pyyaml", file=sys.stderr)
    raise SystemExit(2)

VERSION = "0.1.0"
SKILL = Path(__file__).resolve().parents[1]
TEMPLATES = SKILL / "templates"
PROFILES = {
    "report-visual": {"primary": "report-typst", "ext": "pdf", "csl": "abnt"},
    "journal-scientific": {"primary": "pdf", "ext": "pdf", "csl": "acs"},
    "word-editable": {"primary": "docx", "ext": "docx", "csl": "abnt"},
}
CSL_FILES = {"abnt": "associacao-brasileira-de-normas-tecnicas.csl", "acs": "american-chemical-society.csl"}
FORMAT_EXT = {"report-typst": "pdf", "typst": "pdf", "pdf": "pdf", "docx": "docx"}
CROSSREF_PREFIXES = ("fig-", "tbl-", "eq-", "sec-", "lst-", "thm-", "lem-", "cor-", "prp-", "cnj-", "def-",
                     "exm-", "exr-")


class PubError(Exception):
    pass


# ----------------------------------------------------------------- helpers

def now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(cmd: list[str], cwd: Path | None = None, timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                          encoding="utf-8", errors="replace")


def tool_version(cmd: list[str]) -> str | None:
    try:
        out = run(cmd, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    text = (out.stdout or out.stderr).strip().splitlines()
    return text[0].strip() if out.returncode == 0 and text else None


def front_matter(qmd: Path) -> tuple[dict, str]:
    text = qmd.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        raise PubError(f"{qmd.name}: bloco YAML inicial sem fechamento '---'")
    try:
        meta = yaml.safe_load(text[3:end]) or {}
    except yaml.YAMLError as exc:
        raise PubError(f"{qmd.name}: YAML inválido ({exc})") from exc
    return meta, text[end + 4:]


def profile_of(meta: dict) -> str:
    prof = ((meta.get("uah-publish") or {}).get("profile")) or "report-visual"
    if prof not in PROFILES:
        raise PubError(f"perfil desconhecido {prof!r}; use {', '.join(PROFILES)}")
    return prof


def formats_of(meta: dict) -> list[str]:
    fmt = meta.get("format")
    if isinstance(fmt, str):
        return [fmt]
    if isinstance(fmt, dict):
        return list(fmt)
    return []


def doc_paths(root: Path) -> tuple[Path, Path]:
    root = root.resolve()
    qmd = root / "document.qmd"
    if not qmd.is_file():
        raise PubError(f"{qmd} não existe (rode `pubdoc.py new {root}`)")
    return root, qmd


# --------------------------------------------------------------------- new

def scaffold_meta(profile: str, title: str, lang: str, csl_name: str, with_docx: bool) -> dict:
    meta: dict = {
        "title": title,
        "author": [{"name": "Autor responsável", "affiliations": ["Instituição"]}],
        "date": _dt.date.today().isoformat(),
        "lang": lang,
        "abstract": "Resumo em um parágrafo.",
        "bibliography": "references.bib",
        "csl": f"csl/{CSL_FILES[csl_name]}",
        "reference-section-title": "Referências" if lang.startswith("pt") else "References",
        "abstract-title": "Resumo" if lang.startswith("pt") else "Abstract",
        "uah-publish": {"profile": profile, "page-limit": None},
    }
    fmts: dict = {}
    if profile == "report-visual":
        meta.update({"institution": "Instituição", "report-number": "RT-0000-00", "accent-color": "#1f4e79"})
        fmts["report-typst"] = {"toc": True}
    elif profile == "journal-scientific":
        fmts["pdf"] = {"pdf-engine": "xelatex", "keep-tex": True, "number-sections": True,
                       "documentclass": "article", "papersize": "a4", "geometry": ["margin=2.5cm"]}
    if profile == "word-editable" or with_docx:
        fmts["docx"] = {"reference-doc": "templates/reference-abnt.docx", "toc": profile == "word-editable",
                        "number-sections": True}
    meta["format"] = fmts
    return meta


BODY = """
# Introdução

Contexto e objetivo. Cite assim [@exemplo2026] e referencie a @fig-exemplo e a @tbl-exemplo.

# Métodos

$$ E = mc^2 $$ {#eq-exemplo}

# Resultados

| Grandeza | Valor |
|---|---:|
| A | 1,00 |

: Legenda da tabela. {#tbl-exemplo}

![Legenda da figura.](assets/exemplo.svg){#fig-exemplo fig-alt="Descreva a figura para leitores de tela" width=70%}

# Conclusões
"""

BIB = """@article{exemplo2026,
  author = {Sobrenome, Nome},
  title = {Título do artigo de exemplo},
  journal = {Revista Exemplo},
  year = {2026},
  volume = {1},
  pages = {1--10},
  doi = {10.0000/exemplo}
}
"""

SVG = ('<svg xmlns="http://www.w3.org/2000/svg" width="400" height="160"><rect width="400" height="160" '
       'fill="#f4f7fb"/><text x="200" y="85" text-anchor="middle" font-family="sans-serif" font-size="16">'
       'Substitua por uma figura real</text></svg>')


def cmd_new(root: Path, profile: str, title: str, lang: str, csl: str | None, with_docx: bool, force: bool) -> None:
    if profile not in PROFILES:
        raise PubError(f"perfil desconhecido {profile!r}; use {', '.join(PROFILES)}")
    root = root.resolve()
    if (root / "document.qmd").exists() and not force:
        raise PubError(f"{root}/document.qmd já existe (use --force para recriar só os templates)")
    csl_name = csl or PROFILES[profile]["csl"]
    if csl_name not in CSL_FILES:
        raise PubError(f"estilo de citação desconhecido {csl_name!r}; use {', '.join(CSL_FILES)}")
    for sub in ("assets", "outputs", "csl", "templates"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    shutil.copy2(TEMPLATES / "csl" / CSL_FILES[csl_name], root / "csl" / CSL_FILES[csl_name])
    if profile == "report-visual":
        dest = root / "_extensions" / "uah" / "report"
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(TEMPLATES / "_extensions" / "uah" / "report", dest)
    if profile == "word-editable" or with_docx:
        shutil.copy2(TEMPLATES / "word" / "reference-abnt.docx", root / "templates" / "reference-abnt.docx")
    if not (root / "document.qmd").exists():
        meta = scaffold_meta(profile, title, lang, csl_name, with_docx)
        text = "---\n" + yaml.safe_dump(meta, allow_unicode=True, sort_keys=False) + "---\n" + BODY
        (root / "document.qmd").write_text(text, encoding="utf-8")
        (root / "references.bib").write_text(BIB, encoding="utf-8")
        (root / "assets" / "exemplo.svg").write_text(SVG, encoding="utf-8")
    quarto_yml = root / "_quarto.yml"
    if not quarto_yml.exists():
        quarto_yml.write_text(f"project:\n  type: default\n  output-dir: outputs\nlang: {lang}\n", encoding="utf-8")
    print(f"new: {root} · perfil {profile} · citação {csl_name}" + (" · +docx" if with_docx else ""))
    print("Próximos passos: escreva document.qmd → pubdoc.py preflight → pubdoc.py render → pubdoc.py verify")


# --------------------------------------------------------------- preflight

CITE_RE = re.compile(r"(?<![\w.@])@([A-Za-z0-9_][\w:.#$%&+?<>~/-]*[\w])")
LABEL_RE = re.compile(r"\{[^}]*#((?:%s)[\w-]+)[^}]*\}" % "|".join(CROSSREF_PREFIXES))
CHUNK_LABEL_RE = re.compile(r"^#\|\s*label:\s*((?:%s)[\w-]+)\s*$" % "|".join(CROSSREF_PREFIXES), re.M)
IMG_RE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)(\{[^}]*\})?")
BIB_KEY_RE = re.compile(r"@\w+\s*\{\s*([^,\s]+)\s*,")


def strip_code(body: str) -> str:
    body = re.sub(r"```.*?```", "", body, flags=re.S)
    return re.sub(r"`[^`\n]*`", "", body)


def cmd_preflight(root: Path) -> int:
    root, qmd = doc_paths(root)
    results: list[tuple[str, str]] = []
    add = lambda level, msg: results.append((level, msg))  # noqa: E731
    meta, body = front_matter(qmd)
    profile = profile_of(meta)
    add("OK", f"perfil {profile}; formatos: {', '.join(formats_of(meta)) or '(nenhum)'}")
    for key in ("title", "lang"):
        if not meta.get(key):
            add("FAIL", f"metadado obrigatório ausente: {key}")
    if not meta.get("author"):
        add("WARN", "sem autor (author)")
    if not formats_of(meta):
        add("FAIL", "nenhum formato em `format:`")
    if profile == "report-visual" and "report-typst" in formats_of(meta) and \
            not (root / "_extensions" / "uah" / "report" / "_extension.yml").is_file():
        add("FAIL", "_extensions/uah/report ausente (rode `pubdoc.py new . --profile report-visual --force`)")
    docx_cfg = (meta.get("format") or {}).get("docx") if isinstance(meta.get("format"), dict) else None
    if isinstance(docx_cfg, dict) and docx_cfg.get("reference-doc") and not (root / docx_cfg["reference-doc"]).is_file():
        add("FAIL", f"reference-doc não encontrado: {docx_cfg['reference-doc']}")
    csl = meta.get("csl")
    if csl and not (root / csl).is_file():
        add("FAIL", f"estilo CSL não encontrado: {csl}")

    text = strip_code(body)
    labels = set(LABEL_RE.findall(text)) | set(CHUNK_LABEL_RE.findall(body))
    refs = set(CITE_RE.findall(text))
    crossrefs = {r for r in refs if r.startswith(CROSSREF_PREFIXES)}
    citations = {r for r in refs - crossrefs if "." not in r[-1:]}
    for ref in sorted(crossrefs - labels):
        add("FAIL", f"referência cruzada sem rótulo: @{ref}")
    for label in sorted(labels - crossrefs):
        add("INFO", f"rótulo nunca referenciado: #{label}")

    bibs = meta.get("bibliography") or []
    bibs = [bibs] if isinstance(bibs, str) else bibs
    keys: set[str] = set()
    for bib in bibs:
        path = root / bib
        if not path.is_file():
            add("FAIL", f"bibliografia não encontrada: {bib}")
            continue
        content = path.read_text(encoding="utf-8")
        found = BIB_KEY_RE.findall(content)
        dupes = {k for k in found if found.count(k) > 1}
        if dupes:
            add("FAIL", f"{bib}: chaves duplicadas {sorted(dupes)}")
        keys |= set(found)
        no_id = [k for k, entry in zip(found, re.split(r"(?m)^@", content)[1:])
                 if not re.search(r"(?i)\b(doi|url|isbn)\s*=", entry)]
        if no_id:
            add("INFO", f"{bib}: {len(no_id)} referência(s) sem DOI/URL/ISBN (ex.: {', '.join(no_id[:3])})")
    if citations and not bibs:
        add("FAIL", f"há citações ({len(citations)}) mas nenhuma bibliografia em `bibliography:`")
    missing = sorted(citations - keys) if bibs else []
    for key in missing:
        add("FAIL", f"citação sem entrada na bibliografia: @{key}")
    if bibs:
        unused = sorted(keys - citations)
        if unused:
            add("INFO", f"{len(unused)} entrada(s) não citada(s): {', '.join(unused[:5])}")
        add("OK", f"{len(citations)} citação(ões) distintas, {len(keys)} entrada(s) na bibliografia")

    for path, attrs in IMG_RE.findall(text):
        if re.match(r"https?://", path):
            add("WARN", f"figura remota (exige rede na compilação): {path}")
            continue
        if not (root / path).is_file():
            add("FAIL", f"figura não encontrada: {path}")
        if "fig-alt" not in (attrs or ""):
            add("WARN", f"figura sem texto alternativo (fig-alt): {path}")
        if path.lower().endswith((".png", ".jpg", ".jpeg")) and (root / path).is_file():
            try:
                from PIL import Image  # opcional
                with Image.open(root / path) as im:
                    if min(im.size) < 600:
                        add("WARN", f"figura raster pequena ({im.size[0]}×{im.size[1]} px): {path}; prefira SVG/PDF ou ≥300 dpi")
            except Exception:  # noqa: BLE001
                pass

    for level, msg in results:
        print(f"[{level}] {msg}")
    return 1 if any(level == "FAIL" for level, _ in results) else 0


# ------------------------------------------------------------------ render

def svg_to_pdf(root: Path, body: str) -> list[str]:
    """LaTeX precisa de PDF para figuras SVG; o Quarto reaproveita <figura>.pdf se já existir.
    Usa rsvg-convert se houver; senão, o LibreOffice (headless)."""
    notes = []
    for path, _attrs in IMG_RE.findall(strip_code(body)):
        svg = root / path
        if not path.lower().endswith(".svg") or not svg.is_file():
            continue
        pdf = svg.with_suffix(".pdf")
        if pdf.is_file() and pdf.stat().st_mtime >= svg.stat().st_mtime:
            continue
        if shutil.which("rsvg-convert"):
            out = run(["rsvg-convert", "-f", "pdf", "-a", "-o", str(pdf), str(svg)])
        elif shutil.which("soffice") or shutil.which("libreoffice"):
            office = shutil.which("soffice") or shutil.which("libreoffice")
            out = run([office, "--headless", "--convert-to", "pdf", "--outdir", str(svg.parent), str(svg)], timeout=300)
        else:
            raise PubError(f"figura SVG {path} exige rsvg-convert (librsvg2-bin) ou LibreOffice para o PDF LaTeX")
        if out.returncode != 0 or not pdf.is_file():
            raise PubError(f"falha ao converter {path} para PDF: {(out.stderr or out.stdout).strip()[:200]}")
        notes.append(path)
    return notes


def cmd_render(root: Path, all_formats: bool, to: str | None) -> int:
    root, qmd = doc_paths(root)
    meta, body = front_matter(qmd)
    profile = profile_of(meta)
    fmts = [to] if to else (formats_of(meta) if all_formats else [PROFILES[profile]["primary"]])
    if shutil.which("quarto") is None:
        raise PubError("quarto não encontrado no PATH")
    status = 0
    for fmt in fmts:
        if fmt == "pdf":
            for path in svg_to_pdf(root, body):
                print(f"svg→pdf: {path} (para o LaTeX)")
        out = run(["quarto", "render", qmd.name, "--to", fmt], cwd=root)
        ok = out.returncode == 0
        status |= 0 if ok else 1
        print(f"render {fmt}: {'OK' if ok else 'FALHOU'}")
        if not ok:
            print("\n".join((out.stderr or out.stdout).strip().splitlines()[-15:]))
    return status


# ------------------------------------------------------------------ verify

def contact_sheet(pngs: list[Path], dest: Path) -> bool:
    try:
        from PIL import Image
    except ImportError:
        return False
    images = [Image.open(p) for p in pngs]
    if not images:
        return False
    per_row = min(6, len(images))
    w, h = max(i.width for i in images), max(i.height for i in images)
    rows = (len(images) + per_row - 1) // per_row
    sheet = Image.new("RGB", (per_row * (w + 12) + 12, rows * (h + 12) + 12), (230, 230, 230))
    for idx, im in enumerate(images):
        sheet.paste(im, (12 + (idx % per_row) * (w + 12), 12 + (idx // per_row) * (h + 12)))
    sheet.save(dest)
    return True


def pdf_checks(pdf: Path, review: Path, page_limit, add) -> int:
    pages = None
    info = run(["pdfinfo", str(pdf)]) if shutil.which("pdfinfo") else None
    if info is not None and info.returncode == 0:
        m = re.search(r"^Pages:\s+(\d+)", info.stdout, re.M)
        pages = int(m.group(1)) if m else None
    if pages is None:
        add("WARN", f"{pdf.name}: não foi possível contar páginas (poppler-utils ausente?)")
    else:
        add("OK", f"{pdf.name}: {pages} página(s)")
        if page_limit and pages > int(page_limit):
            add("FAIL", f"{pdf.name}: {pages} páginas excede o limite de {page_limit}")
    if shutil.which("pdffonts"):
        fonts = run(["pdffonts", str(pdf)])
        lines = fonts.stdout.splitlines()[2:]
        not_emb = [ln.split()[0] for ln in lines if ln.split() and len(ln.split()) >= 5 and " no " in f" {ln} "
                   and ln.split()[-5] == "no"]
        if not_emb:
            add("FAIL", f"{pdf.name}: fontes não embutidas: {', '.join(not_emb)}")
        else:
            add("OK", f"{pdf.name}: todas as fontes embutidas")
    if shutil.which("pdftotext"):
        text = run(["pdftotext", str(pdf), "-"]).stdout
        problems = []
        if "?@" in text:
            problems.append("referência cruzada não resolvida (?@…)")
        if re.search(r"\[@[\w-]+", text):
            problems.append("citação não processada ([@…])")
        if re.search(r"\?\?", text):
            problems.append("marcador '??' (referência LaTeX não resolvida)")
        for prob in problems:
            add("FAIL", f"{pdf.name}: {prob}")
    if shutil.which("pdftoppm"):
        stem = review / pdf.stem
        run(["pdftoppm", "-r", "45", "-png", str(pdf), str(stem)])
        pngs = sorted(review.glob(f"{pdf.stem}-*.png"))
        sheet = review / f"{pdf.stem}-contato.png"
        if contact_sheet(pngs, sheet):
            add("REVIEW", f"inspeção visual: abra {sheet.relative_to(review.parent.parent)} (e páginas {pdf.stem}-N.png)")
    return pages or 0


def docx_checks(docx: Path, review: Path, page_limit, add) -> None:
    try:
        with zipfile.ZipFile(docx) as zf:
            bad = zf.testzip()
            names = set(zf.namelist())
            xml = zf.read("word/document.xml").decode("utf-8", "replace") if "word/document.xml" in names else ""
    except zipfile.BadZipFile:
        add("FAIL", f"{docx.name}: arquivo DOCX corrompido")
        return
    if bad or "word/document.xml" not in names:
        add("FAIL", f"{docx.name}: estrutura OOXML inválida ({bad or 'sem word/document.xml'})")
        return
    equations = xml.count("<m:oMath>") + xml.count("<m:oMath ")
    images = len([n for n in names if n.startswith("word/media/")])
    headings = len(re.findall(r'<w:pStyle w:val="Heading\d"', xml))
    add("OK", f"{docx.name}: OOXML íntegro · {headings} título(s) · {images} imagem(ns) · {equations} equação(ões)")
    if "?@" in xml:
        add("FAIL", f"{docx.name}: referência cruzada não resolvida (?@…)")
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        add("WARN", f"{docx.name}: LibreOffice ausente — sem prévia visual do DOCX")
        return
    if equations:
        math_ok = Path("/usr/lib/libreoffice/program/libsmlo.so").exists() or \
            any(Path(p).exists() for p in ("/usr/lib64/libreoffice/program/libsmlo.so",
                                           "/opt/libreoffice/program/libsmlo.so"))
        if not math_ok:
            add("WARN", f"{docx.name}: o LibreOffice local não tem o módulo Math — a prévia OMITE as {equations} "
                        "equação(ões), mas elas estão no DOCX (instale libreoffice-math para pré-visualizar)")
    tmp = review / "_docx"
    tmp.mkdir(exist_ok=True)
    run([soffice, "--headless", "--convert-to", "pdf", "--outdir", str(tmp), str(docx)], timeout=300)
    pdf = tmp / (docx.stem + ".pdf")
    if not pdf.is_file():
        add("WARN", f"{docx.name}: conversão para prévia falhou")
        return
    target = review / f"{docx.stem}-docx.pdf"
    pdf.replace(target)
    pages = pdf_checks(target, review, page_limit, lambda lvl, msg: add(lvl, msg.replace(target.name, f"{docx.name} (prévia)")))
    del pages


def cmd_verify(root: Path) -> int:
    root, qmd = doc_paths(root)
    meta, _ = front_matter(qmd)
    profile = profile_of(meta)
    page_limit = (meta.get("uah-publish") or {}).get("page-limit")
    outdir = root / "outputs"
    review = outdir / "_review"
    if review.exists():
        shutil.rmtree(review)
    review.mkdir(parents=True)
    results: list[tuple[str, str]] = []
    add = lambda level, msg: results.append((level, msg))  # noqa: E731
    expected = sorted({FORMAT_EXT.get(f, f) for f in formats_of(meta)})
    outputs = []
    for ext in expected:
        path = outdir / f"{qmd.stem}.{ext}"
        if not path.is_file() or path.stat().st_size == 0:
            primary_ext = PROFILES[profile]["ext"]
            add("FAIL" if ext == primary_ext else "WARN", f"saída ausente: outputs/{path.name}"
                + (" (formato principal do perfil)" if ext == primary_ext else " (rode render --all para gerar)"))
            continue
        if path.stat().st_mtime < qmd.stat().st_mtime:
            add("WARN", f"outputs/{path.name} é mais antigo que document.qmd — recompile")
        outputs.append(path)
        if ext == "pdf":
            pdf_checks(path, review, page_limit, add)
        elif ext == "docx":
            docx_checks(path, review, page_limit, add)

    sources = [qmd, root / "_quarto.yml"]
    bibs = meta.get("bibliography") or []
    sources += [root / b for b in ([bibs] if isinstance(bibs, str) else bibs)]
    for folder in ("assets", "csl", "templates", "_extensions"):
        if (root / folder).is_dir():
            sources += [p for p in sorted((root / folder).rglob("*")) if p.is_file()]
    manifest = {
        "pubdoc_version": VERSION,
        "generated_at": now_iso(),
        "profile": profile,
        "tools": {
            "quarto": tool_version(["quarto", "--version"]),
            "pandoc": tool_version(["quarto", "pandoc", "--version"]),
            "typst": tool_version(["quarto", "typst", "--version"]),
            "lualatex": tool_version(["lualatex", "--version"]),
        },
        "sources": {p.relative_to(root).as_posix(): sha256(p) for p in sources if p.is_file()},
        "outputs": {p.relative_to(root).as_posix(): sha256(p) for p in outputs},
        "checks": [{"level": lvl, "message": msg} for lvl, msg in results],
        "accepted": False,
    }
    (outdir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for level, msg in results:
        print(f"[{level}] {msg}")
    print(f"manifesto: outputs/manifest.json · prévia: outputs/_review/")
    print("Lembrete: compilar sem erro não é estar pronto — faça a inspeção visual e a revisão científica.")
    return 1 if any(level == "FAIL" for level, _ in results) else 0


# ------------------------------------------------------------------ doctor

TINY_TEX = "\\documentclass{article}\\usepackage{fontspec}\\begin{document}Olá ação\\end{document}\n"


def cmd_doctor() -> int:
    import tempfile
    rows: list[tuple[str, str, str]] = []
    add = lambda level, name, msg: rows.append((level, name, msg))  # noqa: E731
    q = tool_version(["quarto", "--version"])
    add("OK" if q else "FAIL", "quarto", q or "ausente — instale (traz Pandoc e Typst)")
    if q:
        add("OK", "pandoc", tool_version(["quarto", "pandoc", "--version"]) or "?")
        add("OK", "typst", tool_version(["quarto", "typst", "--version"]) or "?")
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "t.tex").write_text(TINY_TEX, encoding="utf-8")
        for engine in ("xelatex", "lualatex", "pdflatex"):
            if not shutil.which(engine):
                add("INFO", engine, "ausente")
                continue
            src = "t.tex"
            if engine == "pdflatex":
                (Path(tmp) / "p.tex").write_text(TINY_TEX.replace("\\usepackage{fontspec}", ""), encoding="utf-8")
                src = "p.tex"
            out = run([engine, "-interaction=nonstopmode", "-halt-on-error", src], cwd=Path(tmp), timeout=300)
            add("OK" if out.returncode == 0 else "WARN", engine,
                "compila" if out.returncode == 0 else "instalado mas falha ao compilar (fontes/pacotes); use outro motor")
    add("OK" if shutil.which("rsvg-convert") else "INFO", "rsvg-convert",
        "presente" if shutil.which("rsvg-convert") else "ausente — SVG→PDF via LibreOffice (fallback automático)")
    office = shutil.which("soffice") or shutil.which("libreoffice")
    add("OK" if office else "WARN", "libreoffice", "presente" if office else "ausente — sem prévia de DOCX")
    if office:
        math_ok = any(Path(p).exists() for p in ("/usr/lib/libreoffice/program/libsmlo.so",
                                                 "/usr/lib64/libreoffice/program/libsmlo.so",
                                                 "/opt/libreoffice/program/libsmlo.so"))
        add("OK" if math_ok else "INFO", "libreoffice-math",
            "presente" if math_ok else "ausente — prévia do DOCX omite equações (o arquivo continua correto)")
    for tool in ("pdfinfo", "pdffonts", "pdftotext", "pdftoppm"):
        add("OK" if shutil.which(tool) else "WARN", tool, "presente" if shutil.which(tool) else "ausente (poppler-utils)")
    try:
        import PIL  # noqa: F401
        add("OK", "Pillow", "presente (folha de contato)")
    except ImportError:
        add("INFO", "Pillow", "ausente — sem folha de contato, só páginas PNG")
    for level, name, msg in rows:
        print(f"[{level}] {name}: {msg}")
    return 1 if any(level == "FAIL" for level, _, _ in rows) else 0


# -------------------------------------------------------------------- main

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pubdoc.py", description=__doc__.splitlines()[0])
    parser.add_argument("--version", action="version", version=f"pubdoc {VERSION}")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("new", help="cria a estrutura de publicação")
    p.add_argument("dir", nargs="?", default="publication")
    p.add_argument("--profile", choices=list(PROFILES), default="report-visual")
    p.add_argument("--title", default="Título do documento")
    p.add_argument("--lang", default="pt-BR")
    p.add_argument("--csl", choices=list(CSL_FILES), help="estilo de citação (padrão do perfil)")
    p.add_argument("--with-docx", action="store_true", help="habilita também a saída DOCX editável")
    p.add_argument("--force", action="store_true", help="recopia templates sem tocar no texto")
    sub.add_parser("doctor", help="testa as ferramentas instaladas")
    for name in ("preflight", "verify"):
        sp = sub.add_parser(name)
        sp.add_argument("dir", nargs="?", default="publication")
    p = sub.add_parser("render", help="compila com quarto")
    p.add_argument("dir", nargs="?", default="publication")
    p.add_argument("--all", action="store_true", help="todos os formatos do documento (entrega)")
    p.add_argument("--to", help="um formato específico (report-typst, pdf, docx)")
    args = parser.parse_args(argv)
    try:
        if args.cmd == "new":
            cmd_new(Path(args.dir), args.profile, args.title, args.lang, args.csl, args.with_docx, args.force)
            return 0
        if args.cmd == "doctor":
            return cmd_doctor()
        if args.cmd == "preflight":
            return cmd_preflight(Path(args.dir))
        if args.cmd == "render":
            return cmd_render(Path(args.dir), args.all, args.to)
        if args.cmd == "verify":
            return cmd_verify(Path(args.dir))
    except PubError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
