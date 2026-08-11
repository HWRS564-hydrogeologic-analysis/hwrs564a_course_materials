#!/usr/bin/env python3
"""Generate D2L content pages from per-week YAML.

Usage
-----
    python d2l/generate.py d2l/weeks/week02.yml
    python d2l/generate.py d2l/weeks/*.yml
    python d2l/generate.py d2l/weeks/*.yml --check    # lint only, write nothing

Then upload the generated file from ``d2l/build/`` to D2L: Content → the week's
module → Upload/Create → Create a File → switch to the HTML source view and
paste, or upload the .html directly to Manage Files and link it.

Why generate rather than edit in D2L
------------------------------------
The 2025 pages drifted: three of thirteen had a Background Material section, two
were missing Time Budget, every page carried an ``id`` left over from the
Measurement course, several had wrong week numbers, and one had a "Lecture
Slides" bullet with no link behind it. Generating from YAML makes those failures
impossible rather than merely unlikely.

Link types in the YAML
----------------------
``url``            an absolute URL, used as-is
``url`` + ``site_relative: true``   joined onto the course site base URL
``course_file``    a file in D2L Manage Files; gets ``?isCourseFile=true``
``dropbox``        a D2L assignment submission rcode; becomes a quicklink
``quiz``           a D2L quiz rcode; becomes a quicklink
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("PyYAML is required:  uv add pyyaml   (or)   pip install pyyaml")


# --------------------------------------------------------------------------
# course-wide constants — change these in one place, every page follows
# --------------------------------------------------------------------------

SITE_BASE = ("https://hwrs564-hydrogeologic-analysis.github.io/"
             "hwrs564a_course_materials/")
RECITATION_URL = "/d2l/home/1430974"
D2L_ORG_UNIT = "1779485"
QUICKLINK = ("/d2l/common/dialogs/quickLink/quickLink.d2l"
             "?ou={ou}&type={kind}&rcode={rcode}")

REQUIRED_SECTIONS = ["time_budget", "background", "class_material",
                     "assignments", "bonus"]
EMPTY_NOTICE = "Nothing required this week."

_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_CODE = re.compile(r"`([^`]+)`")


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def inline(text: str) -> str:
    """Escape, then apply the small subset of markdown we allow in bullets."""
    out = html.escape(str(text), quote=False)
    out = _BOLD.sub(r"<strong>\1</strong>", out)
    out = _CODE.sub(r"<code>\1</code>", out)
    return out


def resolve_url(item: dict, where: str) -> str | None:
    """Turn one of the five link forms into a single href."""
    if item.get("dropbox"):
        return QUICKLINK.format(
            ou=D2L_ORG_UNIT, kind="dropbox", rcode=item["dropbox"]
        )
    # Quizzes are 10% of the grade and there are twelve of them, so a weekly
    # page that mentions one has to link to it like anything else.
    if item.get("quiz"):
        return QUICKLINK.format(ou=D2L_ORG_UNIT, kind="quiz", rcode=item["quiz"])
    if item.get("course_file"):
        return f"{item['course_file']}?isCourseFile=true"
    url = item.get("url")
    if not url:
        return None
    if item.get("site_relative"):
        return SITE_BASE + str(url).lstrip("/")
    return str(url)


def render_items(items, where: str, problems: list[str]) -> str:
    """Render one section's <li> elements, or the empty notice."""
    if not items:
        return f'    <li><em>{EMPTY_NOTICE}</em></li>'

    lines = []
    for i, item in enumerate(items, start=1):
        # A bare string is allowed for plain text bullets (time budget etc.)
        if isinstance(item, str):
            lines.append(f"    <li>{inline(item)}</li>")
            continue

        text = item.get("text")
        if not text:
            problems.append(f"{where} item {i}: missing `text`")
            continue

        href = resolve_url(item, where)
        label = inline(text)

        # An rcode of TBD-* is a deliberate placeholder for a D2L object that
        # doesn't exist yet. The page still generates so it can be reviewed,
        # but the reminder is loud, because a dead quicklink looks like a
        # working link right up until a student clicks it.
        for key in ("dropbox", "quiz"):
            if str(item.get(key, "")).startswith("TBD-"):
                problems.append(
                    f"note: {where} item {i} ({text!r}): {key} rcode is still "
                    f"a placeholder ({item[key]}) — create it in D2L and paste "
                    "the real rcode before this page goes live"
                )

        if href:
            body = (f'<a href="{html.escape(href, quote=True)}" '
                    f'target="_blank" rel="noopener">{label}</a>')
        else:
            # This is exactly the 2025 "Lecture Slides with no link" defect.
            problems.append(
                f"{where} item {i} ({text!r}): no url, course_file, dropbox, "
                "or quiz — would render as unlinked text"
            )
            body = label

        if item.get("note"):
            body += f" &mdash; {inline(item['note'])}"

        lines.append(f"    <li>{body}</li>")

    return "\n".join(lines)


# --------------------------------------------------------------------------
# driver
# --------------------------------------------------------------------------


def build(path: Path, template: str, outdir: Path, check_only: bool):
    spec = yaml.safe_load(path.read_text())
    problems: list[str] = []

    week = spec.get("week")
    title = spec.get("title")
    if week is None:
        problems.append("missing `week`")
    if not title:
        problems.append("missing `title`")

    # The 2025 pages had week numbers that disagreed with the module they sat
    # in. Cheap check: the title should name the same week as the `week` key.
    if week is not None and title:
        found = re.search(r"[Ww]eek\s+(\d+)", title)
        if found and int(found.group(1)) != int(week):
            problems.append(
                f"title says week {found.group(1)} but `week` is {week}"
            )
        if not path.stem.endswith(f"{int(week):02d}"):
            problems.append(
                f"filename {path.name} does not match week {week} "
                f"(expected week{int(week):02d}.yml)"
            )

    for section in REQUIRED_SECTIONS:
        if section not in spec:
            problems.append(f"missing required section `{section}` "
                            "(use `[]` if empty this week)")

    if not spec.get("overview"):
        problems.append("missing `overview` paragraph")

    out_html = (template
                .replace("{{TITLE}}", inline(title or path.stem))
                .replace("{{HEADING}}", inline(title or path.stem))
                .replace("{{OVERVIEW}}", inline(spec.get("overview", "")))
                .replace("{{RECITATION_URL}}", RECITATION_URL)
                .replace("{{TIME_BUDGET}}",
                         render_items(spec.get("time_budget"), "time_budget", problems))
                .replace("{{BACKGROUND}}",
                         render_items(spec.get("background"), "background", problems))
                .replace("{{CLASS_MATERIAL}}",
                         render_items(spec.get("class_material"), "class_material", problems))
                .replace("{{ASSIGNMENTS}}",
                         render_items(spec.get("assignments"), "assignments", problems))
                .replace("{{BONUS}}",
                         render_items(spec.get("bonus"), "bonus", problems)))

    leftover = re.findall(r"\{\{[A-Z_]+\}\}", out_html)
    if leftover:
        problems.append(f"unfilled template placeholders: {', '.join(leftover)}")

    # "note:" lines are advisory: worth printing, not worth failing CI over.
    fatal = [p for p in problems if not p.startswith("note:")]

    label = f"week {week:02d}" if isinstance(week, int) else path.stem
    if problems:
        head = f"{len(fatal)} issue(s)" if fatal else "ok, with reminders"
        print(f"[{'!' if fatal else 'ok'}] {label} ({path.name}) — {head}:")
        for p in problems:
            print(f"      {p}")
    else:
        print(f"[ok] {label} ({path.name})")

    if check_only:
        return not fatal

    outdir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "_",
                  str(title or path.stem).lower()).strip("_")
    out = outdir / f"week_{int(week):02d}_{slug}.html" if isinstance(week, int) \
        else outdir / f"{path.stem}.html"
    out.write_text(out_html, encoding="utf-8")
    print(f"      -> {out}")
    return not fatal


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("yaml_files", nargs="+", type=Path)
    ap.add_argument("-t", "--template", type=Path,
                    default=Path(__file__).parent / "template.html")
    ap.add_argument("-o", "--outdir", type=Path,
                    default=Path(__file__).parent / "build")
    ap.add_argument("--check", action="store_true",
                    help="lint only; do not write files")
    args = ap.parse_args()

    template = args.template.read_text()
    clean = True
    for path in args.yaml_files:
        if not path.exists():
            print(f"error: {path} not found", file=sys.stderr)
            clean = False
            continue
        try:
            clean &= build(path, template, args.outdir, args.check)
        except Exception as exc:
            print(f"error: {path}: {exc}", file=sys.stderr)
            clean = False
    return 0 if clean else 1


if __name__ == "__main__":
    sys.exit(main())
