from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from orchestrator import intake_document, run

SSG_ROOT = Path(__file__).resolve().parents[1] / "repo_synthesis" / "super-skill-creator"
sys.path.insert(0, str(SSG_ROOT))


class OrchestratorRotationTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
