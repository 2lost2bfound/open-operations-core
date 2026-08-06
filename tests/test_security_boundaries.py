from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from orchestrator import intake_document, run

SSG_ROOT = Path(__file__).resolve().parents[1] / "repo_synthesis" / "super-skill-creator"
sys.path.insert(0, str(SSG_ROOT))


class OrchestratorRotationTests(unittest.TestCase):
    def test_mock_provider_call_sequence_rotates_and_logs_indices(self) -> None:
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802 - stdlib handler API
                length = int(self.headers["Content-Length"])
                self.rfile.read(length)
                payload = json.dumps(
                    {"choices": [{"message": {"content": "mock response"}}]}
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *_args):
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server_thread = __import__("threading").Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                env = {
                    "ORCHESTRATOR_BASE_URL": f"http://127.0.0.1:{server.server_port}",
                    "ORCHESTRATOR_MODEL": "claude-web",
                    "LLM_KEY_2": "key-two",
                    "LLM_KEY_2_MODELS": "claude-web",
                    "LLM_KEY_8": "key-eight",
                    "LLM_KEY_8_MODELS": "claude-web",
                }
                with patch.dict(os.environ, env, clear=True), patch.object(
                    run, "vault_root", return_value=Path(directory)
                ):
                    self.assertEqual(run.call_model("one"), "mock response")
                    self.assertEqual(run.call_model("two"), "mock response")
                    self.assertEqual(run.call_model("three"), "mock response")
                log_files = list((Path(directory) / "05-Logs").glob("*.log"))
                log = log_files[0].read_text(encoding="utf-8")
                self.assertEqual(
                    log.splitlines(),
                    ["claude-web → LLM_KEY_2", "claude-web → LLM_KEY_8", "claude-web → LLM_KEY_2"],
                )
        finally:
            server.shutdown()
            server.server_close()

    def test_rotation_uses_stable_key_indices(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / ".runtime" / "rotation.json"
            env = {
                "LLM_KEY_2": "key-two",
                "LLM_KEY_2_MODELS": "claude-web",
                "LLM_KEY_8": "key-eight",
                "LLM_KEY_8_MODELS": "claude-web",
                "LLM_KEY_11": "key-eleven",
                "LLM_KEY_11_MODELS": "claude-web",
            }
            with patch.dict(os.environ, env, clear=True), patch.object(
                run, "rotation_state_path", return_value=state_path
            ):
                self.assertEqual(run.select_key("claude-web")[0], 2)
                run.persist_rotation_choice("claude-web", 2)
                self.assertEqual(run.select_key("claude-web")[0], 8)
                run.persist_rotation_choice("claude-web", 8)
                self.assertEqual(run.select_key("claude-web")[0], 11)

                state_path.unlink()
                state_path.parent.mkdir(mode=0o700, exist_ok=True)
                state_path.write_text(json.dumps({"claude-web": 8}), encoding="utf-8")
                with patch.dict(os.environ, {"LLM_KEY_8": ""}, clear=False):
                    self.assertEqual(run.select_key("claude-web")[0], 2)

    def test_missing_base_url_does_not_create_rotation_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / ".runtime" / "rotation.json"
            env = {
                "ORCHESTRATOR_BASE_URL": "",
                "ORCHESTRATOR_MODEL": "claude-web",
                "LLM_KEY_2": "key-two",
                "LLM_KEY_2_MODELS": "claude-web",
                "LLM_KEY_8": "key-eight",
                "LLM_KEY_8_MODELS": "claude-web",
            }
            with patch.dict(os.environ, env, clear=True), patch.object(
                run, "vault_root", return_value=Path(directory)
            ):
                with self.assertRaisesRegex(RuntimeError, "Missing ORCHESTRATOR_BASE_URL"):
                    run.call_model("test")
            self.assertFalse(state_path.exists())


class DocumentIntakeTests(unittest.TestCase):
    def test_docx_entity_expansion_is_rejected(self) -> None:
        malicious_xml = b'''<?xml version="1.0"?>
<!DOCTYPE lolz [<!ENTITY lol "lol"><!ENTITY lol1 "&lol;&lol;&lol;">]>
<w:document xmlns:w="urn:schemas-microsoft-com:office:word"><w:body><w:p><w:r><w:t>&lol1;</w:t></w:r></w:p></w:body></w:document>'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "hostile.docx"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("word/document.xml", malicious_xml)
            result = intake_document.read_docx(path)
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.text, "")

    def test_secret_flagged_store_requires_restricted_quarantine(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "suspect.txt"
            source.write_text(("pass" + "word: a-likely-secret-value\n") * 6, encoding="utf-8")
            with patch.object(intake_document, "vault_root", return_value=root):
                self.assertEqual(
                    intake_document.main(["--store", "--no-manifest", str(source)]),
                    intake_document.EXIT_USAGE,
                )
                self.assertFalse((root / "07-Mailroom").exists())
                self.assertEqual(
                    intake_document.main(
                        ["--store", "--secure-store", "--no-manifest", str(source)]
                    ),
                    intake_document.EXIT_OK,
                )
            quarantine = root / ".runtime" / "intake-quarantine"
            self.assertTrue(quarantine.exists())
            self.assertEqual(quarantine.stat().st_mode & 0o777, 0o700)
            self.assertEqual(next(quarantine.iterdir()).stat().st_mode & 0o777, 0o600)


@unittest.skipUnless(importlib.util.find_spec("parsel"), "parsel is installed with the SSG package")
class HtmlConversionTests(unittest.TestCase):
    def test_nested_markup_is_converted_as_structure(self) -> None:
        from super_skill_generator.crawler.html_to_md import HtmlToMarkdown

        result = HtmlToMarkdown().convert(
            "<h1>Title</h1><p>Read <strong>this</strong> <a href='/guide'>guide</a>.</p>"
        )
        self.assertIn("# Title", result)
        self.assertIn("**this**", result)
        self.assertIn("[guide](/guide)", result)


@unittest.skipUnless(importlib.util.find_spec("yaml"), "PyYAML is installed with the SSG package")
class CrawlerSafetyTests(unittest.TestCase):
    def test_private_network_is_blocked_and_frontmatter_is_serialized(self) -> None:
        from super_skill_generator.config import CrawlConfig
        from super_skill_generator.crawler.engine import CrawlEngine
        import yaml

        engine = CrawlEngine(CrawlConfig())
        with self.assertRaises(ValueError):
            engine._validate_url("http://127.0.0.1:8080/")
        rendered = engine._build_frontmatter(
            {"name": "demo", "description": "line one\nline two", "metadata.url": "https://example.com"}
        )
        parsed = yaml.safe_load(rendered.split("---", 2)[1])
        self.assertEqual(parsed["description"], "line one\nline two")
        engine._client.close()


class InstallSafetyTests(unittest.TestCase):
    def test_install_is_dry_run_and_force_keeps_backup(self) -> None:
        from super_skill_generator.platforms.adapters.native import NativeAdapter

        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            source = home / "skill"
            source.mkdir()
            (source / "SKILL.md").write_text("version one", encoding="utf-8")
            with patch("pathlib.Path.home", return_value=home):
                adapter = NativeAdapter("codex")
                target = adapter.install(source)
                self.assertFalse(target.exists())
                adapter.install(source, dry_run=False)
                with self.assertRaises(FileExistsError):
                    adapter.install(source, dry_run=False)
                (source / "SKILL.md").write_text("version two", encoding="utf-8")
                adapter.install(source, force=True, dry_run=False)
            self.assertEqual((target / "SKILL.md").read_text(encoding="utf-8"), "version two")
            backups = list(target.parent.glob("skill.backup-*"))
            self.assertEqual(len(backups), 1)
            self.assertEqual((backups[0] / "SKILL.md").read_text(encoding="utf-8"), "version one")


class ScannerSafetyTests(unittest.TestCase):
    def test_scanner_distinguishes_references_from_exposed_values(self) -> None:
        from super_skill_generator.quality.security import SecurityScanner

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "skill.md"
            path.write_text("API_" + "KEY=${API_KEY}\n", encoding="utf-8")
            self.assertEqual(SecurityScanner().scan(path).severity, "medium")
            path.write_text("API_" + 'KEY="prod-secret-value-123456"\n', encoding="utf-8")
            self.assertEqual(SecurityScanner().scan(path).severity, "high")


if __name__ == "__main__":
    unittest.main()
