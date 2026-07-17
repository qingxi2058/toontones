#!/usr/bin/env python3
"""Validate the deployable ToonTones static site without third-party packages."""

from __future__ import annotations

import json
import posixpath
import re
import sys
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ORIGIN = "https://toontones.net"
PRIVATE_PREFIXES = {
    ".claude",
    ".git",
    ".vercel",
    "automation",
    "backlink-agent",
    "execution",
    "scripts",
    "tmp",
    "toontones",
}


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_count = 0
        self.in_title = False
        self.title_parts: list[str] = []
        self.h1_count = 0
        self.descriptions: list[str] = []
        self.canonicals: list[str] = []
        self.references: list[str] = []
        self.in_json_ld = False
        self.json_ld_parts: list[str] = []
        self.json_ld_blocks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "title":
            self.title_count += 1
            self.in_title = True
        elif tag == "h1":
            self.h1_count += 1
        elif tag == "meta" and values.get("name", "").lower() == "description":
            self.descriptions.append(values.get("content", ""))
        elif tag == "link" and values.get("rel", "").lower() == "canonical":
            self.canonicals.append(values.get("href", ""))
        elif tag == "script" and values.get("type", "").lower() == "application/ld+json":
            self.in_json_ld = True
            self.json_ld_parts = []

        for key in ("href", "src"):
            if values.get(key):
                self.references.append(values[key] or "")

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False
        elif tag == "script" and self.in_json_ld:
            self.in_json_ld = False
            self.json_ld_blocks.append("".join(self.json_ld_parts).strip())

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)
        if self.in_json_ld:
            self.json_ld_parts.append(data)


def normalized_url(value: str) -> str:
    cleaned = value.split("#", 1)[0].split("?", 1)[0]
    cleaned = cleaned.replace("https://www.toontones.net", ORIGIN)
    if cleaned.startswith(ORIGIN):
        path = cleaned[len(ORIGIN) :] or "/"
    else:
        path = cleaned or "/"
    if path != "/" and not Path(path).suffix and not path.endswith("/"):
        path += "/"
    return ORIGIN + path


def local_target(reference: str, page_url: str) -> Path | None:
    if not reference or reference.startswith(("#", "mailto:", "tel:", "javascript:", "data:")):
        return None
    cleaned = reference.split("#", 1)[0].split("?", 1)[0]
    if cleaned.startswith(("http://", "https://")):
        if cleaned.startswith(ORIGIN):
            cleaned = cleaned[len(ORIGIN) :] or "/"
        elif cleaned.startswith("https://www.toontones.net"):
            cleaned = cleaned[len("https://www.toontones.net") :] or "/"
        else:
            return None

    if cleaned.startswith("/"):
        path = cleaned
    else:
        page_path = page_url[len(ORIGIN) :] or "/"
        path = posixpath.normpath(posixpath.join(posixpath.dirname(page_path), cleaned))
        if not path.startswith("/"):
            path = "/" + path

    relative = path.lstrip("/")
    if not relative:
        return ROOT / "index.html"
    candidate = ROOT / relative
    if path.endswith("/") or not candidate.suffix:
        candidate /= "index.html"
    return candidate


def main() -> int:
    errors: list[str] = []
    sitemap_path = ROOT / "sitemap.xml"
    try:
        sitemap_text = sitemap_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        print(f"FAIL sitemap.xml: {exc}")
        return 1
    if "<urlset" not in sitemap_text or "</urlset>" not in sitemap_text:
        errors.append("sitemap.xml is missing its urlset root")
    urls = [value.strip() for value in re.findall(r"<loc>\s*([^<]+?)\s*</loc>", sitemap_text)]
    if len(urls) != len(set(urls)):
        errors.append("sitemap.xml contains duplicate URLs")

    sitemap_paths: set[Path] = set()
    for url in urls:
        if not url.startswith(ORIGIN + "/"):
            errors.append(f"sitemap URL is outside the canonical origin: {url}")
            continue
        relative = url[len(ORIGIN) :].lstrip("/")
        page_path = ROOT / (relative or "index.html")
        if relative:
            page_path /= "index.html"
        sitemap_paths.add(page_path.resolve())
        if not page_path.is_file():
            errors.append(f"sitemap target is missing: {url} -> {page_path.relative_to(ROOT)}")

    public_pages = {
        path.resolve()
        for path in ROOT.rglob("index.html")
        if not any(part in PRIVATE_PREFIXES for part in path.relative_to(ROOT).parts)
    }
    for page_path in sorted(public_pages - sitemap_paths):
        errors.append(f"public page is missing from sitemap: {page_path.relative_to(ROOT)}")

    for page_path in sorted(sitemap_paths):
        if not page_path.is_file():
            continue
        relative = page_path.relative_to(ROOT)
        page_url = ORIGIN + ("/" if relative == Path("index.html") else f"/{relative.parent.as_posix()}/")
        parser = PageParser()
        try:
            parser.feed(page_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError) as exc:
            errors.append(f"cannot read {relative}: {exc}")
            continue

        title = "".join(parser.title_parts).strip()
        if parser.title_count != 1 or not title:
            errors.append(f"{relative}: expected one non-empty title, found {parser.title_count}")
        if len(parser.descriptions) != 1 or not parser.descriptions[0].strip():
            errors.append(f"{relative}: expected one non-empty meta description")
        if parser.h1_count != 1:
            errors.append(f"{relative}: expected one H1, found {parser.h1_count}")
        if len(parser.canonicals) != 1:
            errors.append(f"{relative}: expected one canonical, found {len(parser.canonicals)}")
        elif normalized_url(parser.canonicals[0]) != normalized_url(page_url):
            errors.append(
                f"{relative}: canonical mismatch: {parser.canonicals[0]} != {page_url}"
            )

        for index, block in enumerate(parser.json_ld_blocks, start=1):
            try:
                json.loads(block)
            except json.JSONDecodeError as exc:
                errors.append(f"{relative}: JSON-LD block {index} is invalid: {exc}")

        for reference in parser.references:
            target = local_target(reference, page_url)
            if target is None:
                continue
            try:
                target_relative = target.relative_to(ROOT)
            except ValueError:
                errors.append(f"{relative}: local reference escapes site root: {reference}")
                continue
            if any(part in PRIVATE_PREFIXES for part in target_relative.parts):
                errors.append(f"{relative}: links to private path: {reference}")
            elif not target.exists():
                errors.append(f"{relative}: broken local reference: {reference}")

    if errors:
        print(f"FAIL static-site checks: {len(errors)} issue(s)")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"PASS static-site checks: {len(sitemap_paths)} sitemap pages validated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
