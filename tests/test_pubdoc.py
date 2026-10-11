"""Testes do pubdoc (publish-documents).

Unitários: new, preflight e verify, sem compilar.
Integração: compila os três perfis de verdade quando Quarto (e XeLaTeX, para o artigo)
está instalado. Sem a ferramenta, o teste correspondente é pulado com o motivo explícito,
porque depende do ambiente e não da lógica.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PUBDOC = Path(__file__).resolve().parents[1] / "publish-documents" / "scripts" / "pubdoc.py"


def sh(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(PUBDOC), *args], cwd=cwd, capture_output=True, text=True, timeout=900)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def new(self, profile="report-visual", *extra) -> Path:
        out = sh("new", "pub", "--profile", profile, "--title", 'Título "com" aspas: teste', *extra, cwd=self.root)
        self.assertEqual(out.returncode, 0, out.stderr)
        return self.root / "pub"

    def edit(self, pub: Path, old: str, new: str) -> None:
        qmd = pub / "document.qmd"
        text = qmd.read_text(encoding="utf-8")
        self.assertIn(old, text)
        qmd.write_text(text.replace(old, new, 1), encoding="utf-8")


class NewAndPreflight(Base):
    def test_new_creates_profile_assets(self):
        pub = self.new("report-visual", "--with-docx")
        for rel in ("document.qmd", "references.bib", "_quarto.yml", "assets/exemplo.svg",
                    "csl/associacao-brasileira-de-normas-tecnicas.csl", "_extensions/uah/report/_extension.yml",
                    "templates/reference-abnt.docx"):
            self.assertTrue((pub / rel).is_file(), rel)
        journal = sh("new", "art", "--profile", "journal-scientific", cwd=self.root)
        self.assertEqual(journal.returncode, 0, journal.stderr)
        self.assertTrue((self.root / "art/csl/american-chemical-society.csl").is_file())
        self.assertFalse((self.root / "art/_extensions").exists())
        self.assertIn("xelatex", (self.root / "art/document.qmd").read_text())

    def test_new_refuses_to_overwrite_text(self):
        pub = self.new()
        self.edit(pub, "Contexto e objetivo.", "MEU TEXTO.")
        self.assertEqual(sh("new", "pub", cwd=self.root).returncode, 3)
        self.assertEqual(sh("new", "pub", "--force", cwd=self.root).returncode, 0)
        self.assertIn("MEU TEXTO.", (pub / "document.qmd").read_text())

    def test_clean_scaffold_passes_preflight(self):
        pub = self.new()
        out = sh("preflight", "pub", cwd=self.root)
        self.assertEqual(out.returncode, 0, out.stdout)
        self.assertNotIn("[FAIL]", out.stdout)

    def test_preflight_catches_broken_sources(self):
        pub = self.new()
        self.edit(pub, "Cite assim [@exemplo2026]", "Cite assim [@exemplo2026; @inexistente]")
        self.edit(pub, "referencie a @fig-exemplo", "referencie a @fig-exemplo e a @fig-fantasma")
        self.edit(pub, "](assets/exemplo.svg){#fig-exemplo fig-alt=\"Descreva a figura para leitores de tela\"",
                  "](assets/sumiu.svg){#fig-exemplo")
        out = sh("preflight", "pub", cwd=self.root)
        self.assertEqual(out.returncode, 1)
        for text in ("citação sem entrada na bibliografia: @inexistente", "referência cruzada sem rótulo: @fig-fantasma",
                     "figura não encontrada: assets/sumiu.svg", "figura sem texto alternativo"):
            self.assertIn(text, out.stdout)

    def test_emails_and_code_are_not_citations(self):
        pub = self.new()
        self.edit(pub, "# Conclusões", "# Conclusões\n\nContato: fulano@ueg.br.\n\n```python\nx = obj.@decorador\n```")
        out = sh("preflight", "pub", cwd=self.root)
        self.assertNotIn("@ueg", out.stdout)
        self.assertEqual(out.returncode, 0, out.stdout)

    def test_duplicate_bib_keys_fail(self):
        pub = self.new()
        bib = pub / "references.bib"
        bib.write_text(bib.read_text() * 2)
        self.assertIn("chaves duplicadas", sh("preflight", "pub", cwd=self.root).stdout)

    def test_verify_fails_without_primary_output(self):
        pub = self.new()
        out = sh("verify", "pub", cwd=self.root)
        self.assertEqual(out.returncode, 1)
        self.assertIn("saída ausente: outputs/document.pdf (formato principal do perfil)", out.stdout)
        manifest = json.loads((pub / "outputs/manifest.json").read_text())
        self.assertIn("document.qmd", manifest["sources"])
        self.assertFalse(manifest["accepted"])


@unittest.skipUnless(shutil.which("quarto"), "Quarto não instalado neste ambiente")
class RenderIntegration(Base):
    def render_and_verify(self, profile: str, *extra: str) -> tuple[Path, str]:
        pub = self.new(profile, *extra)
        out = sh("render", "pub", "--all", cwd=self.root)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        ver = sh("verify", "pub", cwd=self.root)
        self.assertEqual(ver.returncode, 0, ver.stdout)
        return pub, ver.stdout

    def test_report_visual_pdf_and_docx(self):
        pub, report = self.render_and_verify("report-visual", "--with-docx")
        self.assertIn("document.pdf: todas as fontes embutidas", report)
        self.assertIn("OOXML íntegro", report)
        self.assertTrue((pub / "outputs/_review/document-contato.png").is_file() or "Pillow" in report)
        manifest = json.loads((pub / "outputs/manifest.json").read_text())
        self.assertEqual(set(manifest["outputs"]), {"outputs/document.pdf", "outputs/document.docx"})
        self.assertTrue(manifest["tools"]["typst"])

    @unittest.skipUnless(shutil.which("xelatex"), "XeLaTeX não instalado neste ambiente")
    def test_journal_scientific_pdf(self):
        pub, report = self.render_and_verify("journal-scientific")
        self.assertTrue((pub / "assets/exemplo.pdf").is_file(), "SVG deveria ter sido convertido para o LaTeX")
        self.assertNotIn("não resolvida", report)

    def test_word_editable_docx(self):
        _pub, report = self.render_and_verify("word-editable")
        self.assertIn("1 equação(ões)", report)

    def test_page_limit_enforced(self):
        pub = self.new("report-visual")
        self.edit(pub, "page-limit: null", "page-limit: 1")
        self.assertEqual(sh("render", "pub", cwd=self.root).returncode, 0)
        out = sh("verify", "pub", cwd=self.root)
        self.assertEqual(out.returncode, 1)
        self.assertIn("excede o limite de 1", out.stdout)


if __name__ == "__main__":
    unittest.main()
