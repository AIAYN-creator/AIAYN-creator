"""Build every SVG in the profile README from data, in a light and a dark version.

    python tools/build_svgs.py            # rebuild from assets/data.json
    python tools/build_svgs.py --refresh  # ask GitHub (gh CLI) for fresh numbers first

What it draws: the paper header, the periodic-table tiles (mass = commits), the
legend and the findings cards. The README
picks light or dark with <picture> and prefers-color-scheme. Never edit the
SVGs by hand: change this file and run it.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from xml.sax.saxutils import escape

OWNER = "AIAYN-creator"
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets"
DATA = OUT / "data.json"

SERIF = "Georgia, 'Times New Roman', Times, serif"
SANS = "-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
MONO = "ui-monospace, 'SFMono-Regular', Consolas, 'Liberation Mono', monospace"
MODES = ("light", "dark")

# fill, stroke, strong text, soft text
FAMILIES = {
    "lab": {
        "label": "Chemistry and the lab",
        "light": ("#E1F5EE", "#0F6E56", "#04342C", "#0F6E56"),
        "dark": ("#082A23", "#1D9E75", "#C9F0E2", "#5DCAA5"),
    },
    "agents": {
        "label": "Human-in-the-loop AI",
        "light": ("#EEEDFE", "#534AB7", "#26215C", "#534AB7"),
        "dark": ("#1C1940", "#7F77DD", "#DEDCFA", "#AFA9EC"),
    },
    "side": {
        "label": "Side quests",
        "light": ("#FAECE7", "#993C1D", "#4A1B0C", "#993C1D"),
        "dark": ("#341409", "#D85A30", "#F8D9CD", "#F0997B"),
    },
}

# GitHub's own page colours, so the images sit on the page without a seam
PAGE = {
    "light": {"bg": "#ffffff", "ink": "#1f2328", "soft": "#59636e", "rule": "#d1d9e0", "card": "#f6f8fa"},
    "dark": {"bg": "#0d1117", "ink": "#f0f6fc", "soft": "#9198a1", "rule": "#3d444d", "card": "#151b23"},
}

# symbol, display name, repo, family, one-line tag
ELEMENTS = [
    ("Cc", "Comp. Chemistry", "Computational-Chemistry", "lab", "Gaussian + Bash"),
    ("Lh", "LabHarness", "Lab-Harness", "lab", "data to PDF"),
    ("Bx", "Bib-Exprés", "Bib-Expres", "lab", "citation snowball"),
    ("Ap", "Apuntes.md", "Apuntes.md", "lab", "notes to Obsidian"),
    ("Ms", "Monkey/Scalpel", "monkey-with-a-scalpel", "agents", "LLM lab robotics"),
    ("Hs", "Histos", "Histos", "agents", "human-AI board"),
    ("Ea", "Ego Audit", "Ego-Audit", "agents", "backtest honesty"),
    ("Lu", "Lumen TV", "lumen-tv", "side", "2009 TV, reborn"),
    ("Rc", "Recetas", "Recetas-", "side", "Gantt recipes"),
    ("Mf", "Mi Filmo", "Mi-Filmo", "side", "film diary in git"),
    ("Ty", "Track Your Way", "Habit-Tracker", "side", "local-first habits"),
]

# Findings cards: (file id, family, label, big number, claim). Each claim comes
# from the README of that repository; keep them in sync when a number changes.
FINDINGS = [
    ("rhf", "lab", "Computational Chemistry · Hartree-Fock", "7.6 eV",
     "Restricted Hartree-Fock cannot break a bond: the error left at dissociation of H₂."),
    ("labharness", "lab", "LabHarness · data to paper", "1.3 s",
     "From a CSV to a figure in the PDF. Change a measurement and the fit and the text follow."),
    ("monkey", "agents", "Monkey with a Scalpel · simulated gantry", "88 mm → 9 µm",
     "The agent corrects its own positioning error in 26 iterations. Ideal simulation; hardware is next."),
    ("egoaudit", "agents", "Ego Audit · SPY, 2022–2024", "+14.1 % → +5.3 %",
     "A 20-day moving average after fees and slippage. Buy-and-hold made +19.2 %."),
    ("bibexpres", "lab", "Bib-Exprés · literature search", "200 papers / 22 s",
     "One DOI in, generations of references and citations out, ranked by relevance."),
    ("histos", "agents", "Histos · human-AI task board", "v3",
     "Planned and reviewed card by card in a Histos vault: the tool built with itself."),
    ("apuntes", "lab", "Apuntes.md · handwritten notes", "0 words invented",
     "Scanned biochemistry notes to Markdown, checked word by word against the page."),
    ("lumen", "side", "Lumen TV · one Sunday", "2009",
     "A TV with nothing smart in it, turned into a home dashboard with a phone remote."),
]


# ---------------------------------------------------------------- data

def gh(*args: str) -> str | None:
    try:
        return subprocess.run(["gh", *args], capture_output=True, text=True, check=True,
                              encoding="utf-8").stdout
    except (OSError, subprocess.CalledProcessError):
        return None


def commit_count(repo: str) -> int | None:
    """Commits on the default branch, read from the pagination header."""
    out = gh("api", "-i", f"repos/{OWNER}/{repo}/commits?per_page=1")
    if out is None:
        return None
    m = re.search(r'[?&]page=(\d+)>; rel="last"', out)
    return int(m.group(1)) if m else 1


def load() -> dict:
    return json.loads(DATA.read_text(encoding="utf-8")) if DATA.exists() else {"commits": {}}


def refresh(data: dict) -> dict:
    """Update what GitHub can tell us; keep the old value for anything it can't."""
    for _s, _n, repo, *_ in ELEMENTS:
        n = commit_count(repo)
        if n is not None:
            data["commits"][repo] = n
        print(f"{repo:<26} {data['commits'].get(repo, '?')}")
    DATA.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return data


# ---------------------------------------------------------------- drawing

def svg(width: int, height: int, body: str, title: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">'
        f"<title>{escape(title)}</title>{body}</svg>\n"
    )


def wrap(text: str, width: int) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        if line and len(line) + 1 + len(word) > width:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    return lines + [line] if line else lines


def tile(number: int, el: tuple, mass: int | str, mode: str) -> str:
    sym, name, _repo, fam, tag = el
    fill, stroke, ink, soft = FAMILIES[fam][mode]
    w = h = 150
    body = (
        f'<rect x="1" y="1" width="{w-2}" height="{h-2}" rx="5" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
        f'<text x="12" y="24" font-family="{MONO}" font-size="13" fill="{soft}">{number}</text>'
        f'<text x="{w-12}" y="24" text-anchor="end" font-family="{MONO}" font-size="13" fill="{soft}">{mass}</text>'
        f'<text x="{w/2}" y="90" text-anchor="middle" font-family="{SERIF}" font-size="54" fill="{ink}">{escape(sym)}</text>'
        f'<text x="{w/2}" y="116" text-anchor="middle" font-family="{SANS}" font-size="13" font-weight="600" fill="{ink}">{escape(name)}</text>'
        f'<text x="{w/2}" y="134" text-anchor="middle" font-family="{SANS}" font-size="11" fill="{soft}">{escape(tag)}</text>'
    )
    return svg(w, h, body, f"{number} {sym}: {name}, {tag}, {mass} commits")


def header(mode: str) -> str:
    p = PAGE[mode]
    w, h = 900, 250
    cx = w / 2 + 14
    body = (
        # the preprint stamp running up the left margin
        f'<text transform="translate(26 {h-14}) rotate(-90)" font-family="{SERIF}" font-size="12" fill="{p["soft"]}" letter-spacing="0.5">'
        f"preprint 2611.04 [physics.chem-ph]</text>"
        f'<line x1="44" y1="14" x2="44" y2="{h-14}" stroke="{p["rule"]}" stroke-width="1"/>'
        f'<text x="{cx}" y="92" text-anchor="middle" font-family="{SERIF}" font-size="46" fill="{p["ink"]}">Curiosity Is All You Need</text>'
        f'<text x="{cx}" y="140" text-anchor="middle" font-family="{SERIF}" font-size="21" fill="{p["ink"]}">AIAYN-creator'
        f'<tspan baseline-shift="super" font-size="13">1</tspan></text>'
        f'<text x="{cx}" y="170" text-anchor="middle" font-family="{SERIF}" font-size="15" font-style="italic" fill="{p["soft"]}">'
        f'<tspan font-size="11" baseline-shift="super">1</tspan>Chemistry undergraduate who builds tools for the lab</text>'
        f'<line x1="{cx-170}" y1="200" x2="{cx+170}" y2="200" stroke="{p["rule"]}" stroke-width="1"/>'
        f'<text x="{cx}" y="226" text-anchor="middle" font-family="{SERIF}" font-size="14" fill="{p["soft"]}">'
        f"Being curious saved my life. AI is cool, I guess.</text>"
    )
    return svg(w, h, body, "Curiosity Is All You Need, by AIAYN-creator")


def legend(mode: str) -> str:
    p = PAGE[mode]
    w, h = 900, 40
    x, parts = 0, []
    for fam in FAMILIES.values():
        fill, stroke, _ink, _soft = fam[mode]
        label = fam["label"]
        parts.append(
            f'<rect x="{x+1}" y="12" width="16" height="16" rx="3" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
            f'<text x="{x+26}" y="25" font-family="{SANS}" font-size="14" fill="{p["ink"]}">{escape(label)}</text>'
        )
        x += 34 + int(len(label) * 7.6) + 26
    parts.append(
        f'<text x="{w-2}" y="25" text-anchor="end" font-family="{MONO}" font-size="12" fill="{p["soft"]}">'
        f"top left: atomic number · top right: mass (commits)</text>"
    )
    return svg(w, h, "".join(parts), "Legend: three families of projects; the number on the right is the commit count")


def finding(card: tuple, mode: str) -> str:
    _id, fam, label, number, claim = card
    p = PAGE[mode]
    _fill, stroke, _ink, soft = FAMILIES[fam][mode]
    w, h = 440, 176
    lines = wrap(claim, 52)[:3]
    body = (
        f'<rect x="0.5" y="0.5" width="{w-1}" height="{h-1}" rx="6" fill="{p["card"]}" stroke="{p["rule"]}"/>'
        f'<rect x="0" y="18" width="4" height="{h-36}" fill="{stroke}"/>'
        f'<text x="24" y="34" font-family="{SANS}" font-size="12" fill="{soft}" letter-spacing="0.3">{escape(label)}</text>'
        f'<text x="24" y="86" font-family="{SERIF}" font-size="40" fill="{p["ink"]}">{escape(number)}</text>'
    )
    for i, line in enumerate(lines):
        body += (f'<text x="24" y="{118 + i*20}" font-family="{SANS}" font-size="14" fill="{p["soft"]}">'
                 f"{escape(line)}</text>")
    return svg(w, h, body, f"{label}: {number}. {claim}")


def main() -> None:
    data = refresh(load()) if "--refresh" in sys.argv else load()
    (OUT / "tiles").mkdir(parents=True, exist_ok=True)
    (OUT / "findings").mkdir(parents=True, exist_ok=True)
    n = 0
    for mode in MODES:
        files = {
            f"header-{mode}.svg": header(mode),
            f"legend-{mode}.svg": legend(mode),
        }
        for i, el in enumerate(ELEMENTS, start=1):
            files[f"tiles/{el[0].lower()}-{mode}.svg"] = tile(i, el, data["commits"].get(el[2], "?"), mode)
        for card in FINDINGS:
            files[f"findings/{card[0]}-{mode}.svg"] = finding(card, mode)
        for name, text in files.items():
            (OUT / name).write_text(text, encoding="utf-8")
        n += len(files)
    print(f"wrote {n} SVGs to {OUT}")


if __name__ == "__main__":
    main()
