"""Documentation style checks."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FILES = [
    ROOT / "README.md",
    ROOT / "pyproject.toml",
    *sorted((ROOT / "fieldbridge").rglob("*.py")),
]

FORBIDDEN = {
    "\u2013": "en dash",
    "\u2014": "em dash",
    "&ndash;": "en dash entity",
    "&mdash;": "em dash entity",
    "&#8211;": "en dash entity",
    "&#8212;": "em dash entity",
}


def test_documentation_has_no_typographic_dashes():
    offenders = []
    for path in FILES:
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), 1):
            for needle, label in FORBIDDEN.items():
                if needle in line:
                    offenders.append(
                        f"{path.relative_to(ROOT)}:{lineno}: {label}"
                    )
    assert not offenders, (
        "Remove typographic dashes from the documentation:\n"
        + "\n".join(offenders)
    )
