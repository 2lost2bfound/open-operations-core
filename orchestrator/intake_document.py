#!/usr/bin/env python3
"""Classify an incoming document and write a Mailroom intake manifest."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import re
import shutil
import subprocess
import sys
import textwrap
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from defusedxml import ElementTree


EXIT_OK = 0
EXIT_USAGE = 2
MAX_TEXT_BYTES = 2_000_000
CLASSIFICATION_TEXT_BYTES = 256 * 1024
SECRET_SCAN_CHUNK_BYTES = 64 * 1024
SECRET_SCAN_OVERLAP_BYTES = 256
MANIFEST_VERSION = 1


ROUTE_FLOORS = {
    "skill_conversion": "Basement — File Intake & Skill Conversion",
    "reference_index": "08-File-Storage / 06-Tutorials-and-Guides",
    "knowledge_retrieval": "Knowledge & Retrieval",
    "project_brief": "03-Projects",
    "video_production": "04-Video-Production",
    "security_review": "Security — Secrets & Access",
    "open_question": "Orchestrator Open Questions",
}


NEXT_STEPS = {
    "skill_conversion": "Verify source permission, place source in 08-File-Storage/skill-candidates/, then run the book-to-skill workflow.",
    "reference_index": "Store the source under 08-File-Storage/references/ and summarize or link it from the relevant reference index.",
    "knowledge_retrieval": "Extract clean text, store it in 08-File-Storage/extracted-text/, and queue it for the Knowledge & Retrieval floor.",
    "project_brief": "Create or update a project folder under 03-Projects/ with brief.md, tasks.md, and log.md.",
    "video_production": "Route to 04-Video-Production or create a video/content job under 03-Projects/.",
    "security_review": "Do not summarize content. Move handling to Security — Secrets & Access and redact before any downstream processing.",
    "open_question": "Ask the human/orchestrator to clarify what this document is and whether it may be stored or transformed.",
}


TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".markdown",
    ".rst",
    ".csv",
    ".tsv",
    ".json",
    ".jsonl",
    ".yaml",
    ".yml",
    ".xml",
    ".html",
    ".htm",
    ".log",
}


SIGNALS = {
    "skill_conversion": [
        "step-by-step",
        "workflow",
        "procedure",
        "checklist",
        "run this",
        "command",
        "install",
        "configure",
        "troubleshoot",
        "how to",
        "use when",
        "verification",
        "red flags",
        "common mistakes",
        "script",
        "cli",
    ],
    "reference_index": [
        "chapter",
        "lesson",
        "curriculum",
        "course",
        "tutorial",
        "overview",
        "introduction",
        "concept",
        "theory",
        "background",
        "glossary",
        "reference",
        "guide",
    ],
    "knowledge_retrieval": [
        "api reference",
        "manual",
        "specification",
        "schema",
        "endpoint",
        "sdk",
        "documentation",
        "parameters",
        "configuration reference",
        "class ",
        "function ",
        "method ",
    ],
    "project_brief": [
        "objective",
        "requirements",
        "acceptance criteria",
        "deliverable",
        "milestone",
        "deadline",
        "task list",
        "project brief",
        "roadmap",
        "scope",
        "stakeholder",
    ],
    "video_production": [
        "youtube",
        "shorts",
        "channel",
        "script",
        "storyboard",
        "voiceover",
        "b-roll",
        "thumbnail",
        "episode",
        "tiktok",
        "reels",
        "video production",
    ],
}


SECRET_PATTERNS = [
    re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA |PGP )?PRIVATE KEY-----"),
    re.compile(r"\bapi[_-]?key\b", re.IGNORECASE),
    re.compile(r"\bsecret[_-]?key\b", re.IGNORECASE),
    re.compile(r"\baccess[_-]?token\b", re.IGNORECASE),
    re.compile(r"\bpassword\s*[:=]", re.IGNORECASE),
    re.compile(r"\bsk-[A-Za-z0-9][A-Za-z0-9_-]{16,}\b"),
]


@dataclass
class Extraction:
    status: str
    text: str
    note: str


def vault_root() -> Path:
    return Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip())
    slug = slug.strip("-._")
    return slug[:80] or "document"


def read_text_file(path: Path) -> Extraction:
    data = path.read_bytes()[:MAX_TEXT_BYTES]
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            return Extraction("ok", data.decode(encoding), f"decoded as {encoding}")
        except UnicodeDecodeError:
            continue
    return Extraction("failed", "", "could not decode as text")


def read_docx(path: Path) -> Extraction:
    try:
        with zipfile.ZipFile(path) as archive:
            raw = archive.read("word/document.xml")
    except Exception as exc:
        return Extraction("failed", "", f"docx extraction failed: {exc.__class__.__name__}")

    try:
        root = ElementTree.fromstring(raw)
    except Exception:
        return Extraction("failed", "", "docx XML parse failed")

    pieces = []
    for node in root.iter():
        if node.tag.endswith("}t") and node.text:
            pieces.append(node.text)
        elif node.tag.endswith("}p"):
            pieces.append("\n")
    return Extraction("ok", "\n".join(pieces), "extracted word/document.xml")


def strip_tags(value: str) -> str:
    value = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", value)
    value = re.sub(r"(?s)<[^>]+>", " ", value)
    return html.unescape(re.sub(r"\s+", " ", value))


def read_epub(path: Path) -> Extraction:
    texts = []
    try:
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                lower = name.lower()
                if lower.endswith((".xhtml", ".html", ".htm")):
                    raw = archive.read(name)
                    texts.append(strip_tags(raw.decode("utf-8", errors="ignore")))
                    if sum(len(t) for t in texts) > MAX_TEXT_BYTES:
                        break
    except Exception as exc:
        return Extraction("failed", "", f"epub extraction failed: {exc.__class__.__name__}")

    text = "\n\n".join(texts)
    if not text.strip():
        return Extraction("failed", "", "no readable HTML/XHTML content found in epub")
    return Extraction("ok", text[:MAX_TEXT_BYTES], "extracted HTML/XHTML content from epub")


def read_pdf(path: Path) -> Extraction:
    if shutil.which("pdftotext") is None:
        return Extraction("unsupported", "", "pdftotext is not installed; route requires extraction tool decision")

    try:
        completed = subprocess.run(
            ["pdftotext", str(path), "-"],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        return Extraction("failed", "", "pdftotext timed out")

    if completed.returncode != 0:
        return Extraction("failed", "", "pdftotext failed")
    return Extraction("ok", completed.stdout[:MAX_TEXT_BYTES], "extracted with pdftotext")


def extract_text(path: Path) -> Extraction:
    suffix = path.suffix.lower()
    if suffix in TEXT_EXTENSIONS:
        return read_text_file(path)
    if suffix == ".docx":
        return read_docx(path)
    if suffix == ".epub":
        return read_epub(path)
    if suffix == ".pdf":
        return read_pdf(path)
    if suffix == ".rtf":
        extraction = read_text_file(path)
        cleaned = re.sub(r"[{}\\][A-Za-z0-9*'-]* ?", " ", extraction.text)
        return Extraction(extraction.status, cleaned, "best-effort RTF text cleanup")
    return Extraction("unsupported", "", f"unsupported extension: {suffix or 'none'}")


def count_signals(text: str, words: Iterable[str]) -> int:
    lowered = text.lower()
    return sum(lowered.count(word.lower()) for word in words)


def has_secret_signal(text: str) -> bool:
    sample = text[:MAX_TEXT_BYTES]
    step = max(1, SECRET_SCAN_CHUNK_BYTES - SECRET_SCAN_OVERLAP_BYTES)
    for start in range(0, len(sample), step):
        chunk = sample[start : start + SECRET_SCAN_CHUNK_BYTES]
        if any(pattern.search(chunk) for pattern in SECRET_PATTERNS):
            return True
    return False


def classify(path: Path, extraction: Extraction) -> dict:
    # Keep classification work bounded even when an extractor returns a large,
    # repetitive, or adversarial document. Secret detection remains separate
    # and scans the capped extraction in bounded chunks.
    text = extraction.text[:CLASSIFICATION_TEXT_BYTES]
    reasons: list[str] = []

    if extraction.status != "ok" or len(text.strip()) < 80:
        return {
            "route": "open_question",
            "confidence": "low",
            "scores": {},
            "reasons": [extraction.note, "not enough extracted text to classify safely"],
        }

    if has_secret_signal(text):
        return {
            "route": "security_review",
            "confidence": "high",
            "scores": {"security_review": 99},
            "reasons": ["document contains secret-like or credential-like signals"],
        }

    scores = {route: count_signals(text, terms) for route, terms in SIGNALS.items()}

    command_blocks = len(re.findall(r"(?m)^```", text)) // 2
    numbered_steps = len(re.findall(r"(?m)^\s*\d+[.)]\s+\S+", text))
    bullets = len(re.findall(r"(?m)^\s*[-*]\s+\S+", text))
    headings = len(re.findall(r"(?m)^#{1,4}\s+\S+", text))

    if command_blocks:
        scores["skill_conversion"] += min(command_blocks * 2, 8)
        reasons.append(f"contains {command_blocks} fenced command/code block(s)")
    if numbered_steps >= 3:
        scores["skill_conversion"] += 5
        reasons.append("contains multiple numbered steps")
    if bullets >= 6 and scores["skill_conversion"] > 0:
        scores["skill_conversion"] += 2
        reasons.append("contains checklist/list structure")
    if headings >= 4 and scores["reference_index"] > 0:
        scores["reference_index"] += 2

    sorted_scores = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    top_route, top_score = sorted_scores[0]
    second_score = sorted_scores[1][1] if len(sorted_scores) > 1 else 0

    for route, score in sorted_scores:
        if score:
            reasons.append(f"{route} matched {score} signal(s)")

    if top_score == 0:
        return {
            "route": "reference_index",
            "confidence": "low",
            "scores": scores,
            "reasons": ["text extracted, but no strong route signals were found"],
        }

    if top_score - second_score <= 1 and top_score < 5:
        return {
            "route": "open_question",
            "confidence": "low",
            "scores": scores,
            "reasons": reasons + ["top route was too close to the next route"],
        }

    confidence = "high" if top_score >= 7 and top_score - second_score >= 3 else "medium"
    return {
        "route": top_route,
        "confidence": confidence,
        "scores": scores,
        "reasons": reasons or [f"{top_route} had the strongest route score"],
    }


def write_manifest(root: Path, source: Path, metadata: dict) -> Path:
    manifest_dir = root / "07-Mailroom" / "manifests"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    manifest_path = manifest_dir / f"{timestamp}-{slugify(source.stem)}.md"

    reasons = "\n".join(f"- {reason}" for reason in metadata["reasons"])
    open_questions = ""
    if metadata["route"] == "open_question":
        open_questions = "\n## Open Questions\n\n- What is this document intended to become: skill, reference, project material, or something else?\n"

    content = f"""---
status: triaged
owner-agent: orchestrator
last_updated: {dt.date.today().isoformat()}
type: document-intake-manifest
manifest_version: {MANIFEST_VERSION}
route: {metadata["route"]}
confidence: {metadata["confidence"]}
---

# Document Intake Manifest — {source.name}

## Source

- Path: `{source}`
- SHA-256: `{metadata["sha256"]}`
- Size: {metadata["size_bytes"]} bytes
- Detected type: `{metadata["document_type"]}`
- Extraction status: {metadata["extraction_status"]}
- Extraction note: {metadata["extraction_note"]}

## Route

- Route: `{metadata["route"]}`
- Destination floor: {metadata["destination_floor"]}
- Confidence: {metadata["confidence"]}

## Why

{reasons}

## Recommended next step

{metadata["recommended_next_step"]}
{open_questions}
"""
    manifest_path.write_text(content, encoding="utf-8")
    return manifest_path


def maybe_store_source(root: Path, source: Path) -> Path:
    incoming = root / "07-Mailroom" / "incoming"
    incoming.mkdir(parents=True, exist_ok=True)
    target = incoming / source.name
    if target.exists():
        target = incoming / f"{dt.datetime.now().strftime('%Y%m%d-%H%M%S')}-{source.name}"
    shutil.copy2(source, target)
    return target


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="intake_document.py",
        description="Classify an incoming document and write a Super-Repo Mailroom intake manifest.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """\
            examples:
              python3 orchestrator/intake_document.py notes.md
              python3 orchestrator/intake_document.py --json manual.pdf
              python3 orchestrator/intake_document.py --store tutorial.epub

            exit codes:
              0  classified successfully
              2  invalid input or usage
            """
        ),
    )
    parser.add_argument("path", help="Path to the document to classify.")
    parser.add_argument("--json", action="store_true", help="Write machine-readable JSON to stdout.")
    parser.add_argument("--no-manifest", action="store_true", help="Classify without writing a Mailroom manifest.")
    parser.add_argument("--store", action="store_true", help="Copy the source file into 07-Mailroom/incoming/ after classification.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    root = vault_root()
    source = Path(args.path).expanduser().resolve()
    if not source.exists():
        print(f"error: file does not exist: {source}", file=sys.stderr)
        return EXIT_USAGE
    if not source.is_file():
        print(f"error: path is not a file: {source}", file=sys.stderr)
        return EXIT_USAGE

    extraction = extract_text(source)
    classification = classify(source, extraction)
    metadata = {
        "source_path": str(source),
        "document_type": source.suffix.lower().lstrip(".") or "unknown",
        "sha256": sha256_file(source),
        "size_bytes": source.stat().st_size,
        "extraction_status": extraction.status,
        "extraction_note": extraction.note,
        "route": classification["route"],
        "destination_floor": ROUTE_FLOORS[classification["route"]],
        "confidence": classification["confidence"],
        "scores": classification.get("scores", {}),
        "reasons": classification["reasons"],
        "recommended_next_step": NEXT_STEPS[classification["route"]],
        "manifest_path": None,
        "stored_copy_path": None,
    }

    if not args.no_manifest:
        metadata["manifest_path"] = str(write_manifest(root, source, metadata))
    if args.store:
        metadata["stored_copy_path"] = str(maybe_store_source(root, source))

    if args.json:
        print(json.dumps(metadata, indent=2, sort_keys=True))
    else:
        print(f"ROUTE: {metadata['route']}")
        print(f"FLOOR: {metadata['destination_floor']}")
        print(f"CONFIDENCE: {metadata['confidence']}")
        if metadata["manifest_path"]:
            print(f"MANIFEST: {metadata['manifest_path']}")
        print("NEXT:", metadata["recommended_next_step"])

    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
