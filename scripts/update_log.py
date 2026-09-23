#!/usr/bin/env python3
"""
Refresh the "Recently shipped" table in README.md from the GitHub API.

Standard library only. Rewrites the block between LOG:START and LOG:END.
On any network/API error it leaves README.md untouched and exits 0, so the
profile always shows the last good version.

    GITHUB_TOKEN=... python scripts/update_log.py
    python scripts/update_log.py --fixture sample.json   # offline test

Repo descriptions come from GitHub first, then scripts/notes.json.
Repos listed under "exclude" in notes.json are skipped.
"""
import json
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README = os.path.join(ROOT, "README.md")
NOTES = os.path.join(ROOT, "scripts", "notes.json")
USER = os.environ.get("PROFILE_USER") or os.environ.get("GITHUB_REPOSITORY_OWNER") or "AntoRoshanm"
ROWS = 5
START, END = "<!-- LOG:START -->", "<!-- LOG:END -->"


def fetch():
    url = f"https://api.github.com/users/{USER}/repos?per_page=100&sort=pushed&type=owner"
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{USER}-profile-log",
        **({"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}"}
           if os.environ.get("GITHUB_TOKEN") else {}),
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def pretty(name):
    return re.sub(r"\s+", " ", re.sub(r"[-_]+", " ", name)).strip()


def clip(s, limit=110):
    s = (s or "").strip()
    if len(s) <= limit:
        return s
    return s[:limit].rsplit(" ", 1)[0].rstrip(" ,;:—-") + "…"


def cell(s):
    return (s or "").replace("|", "\\|").replace("\n", " ").strip()


def render(repos, notes):
    skip = {USER.lower(), *[e.lower() for e in notes.get("exclude", [])]}
    picked = [r for r in repos
              if not r.get("fork") and not r.get("archived") and not r.get("private")
              and r["name"].lower() not in skip]
    picked.sort(key=lambda r: r.get("pushed_at") or "", reverse=True)
    lines = ["| Updated | Repository | Language | About |", "|---|---|---|---|"]
    for r in picked[:ROWS]:
        about = r.get("description") or notes.get("describe", {}).get(r["name"]) or "—"
        lines.append(
            f"| `{(r.get('pushed_at') or '')[:10]}` "
            f"| [{cell(pretty(r['name']))}]({r['html_url']}) "
            f"| {cell(r.get('language') or '—')} | {cell(clip(about))} |")
    return "\n".join(lines)


def main():
    notes = {}
    if os.path.exists(NOTES):
        with open(NOTES, encoding="utf-8") as f:
            notes = json.load(f)
    try:
        if "--fixture" in sys.argv:
            with open(sys.argv[sys.argv.index("--fixture") + 1], encoding="utf-8") as f:
                repos = json.load(f)
        else:
            repos = fetch()
        if not isinstance(repos, list):
            raise ValueError(f"unexpected API response: {str(repos)[:200]}")
    except Exception as e:  # keep the last good README
        print(f"::warning::log not refreshed: {e}")
        return 0

    with open(README, encoding="utf-8") as f:
        readme = f.read()
    if START not in readme or END not in readme:
        print("::warning::LOG markers missing from README.md")
        return 0
    block = f"{START}\n{render(repos, notes)}\n{END}"
    updated = re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _: block, readme, flags=re.S)
    if updated != readme:
        with open(README, "w", encoding="utf-8") as f:
            f.write(updated)
        print("README.md log refreshed")
    else:
        print("log already current")
    return 0


if __name__ == "__main__":
    sys.exit(main())
