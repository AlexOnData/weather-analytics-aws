"""One-shot script: rewrite every text file in the project without Romanian diacritics.

Excludes runtime / vendor / cache directories.

The mapping is built with ``chr()`` from numeric code points so the source
file itself contains no diacritics and can be re-run without self-corruption.
"""

from __future__ import annotations

from pathlib import Path

# (lower_codepoint, upper_codepoint, ascii_replacement)
_PAIRS = [
    (0x0103, 0x0102, "a"),  # a-breve
    (0x00E2, 0x00C2, "a"),  # a-circumflex
    (0x00EE, 0x00CE, "i"),  # i-circumflex
    (0x0219, 0x0218, "s"),  # s-comma (modern Romanian)
    (0x015F, 0x015E, "s"),  # s-cedilla (legacy)
    (0x021B, 0x021A, "t"),  # t-comma (modern Romanian)
    (0x0163, 0x0162, "t"),  # t-cedilla (legacy)
]

DIACRITIC_MAP: dict[str, str] = {}
for low, up, ascii_char in _PAIRS:
    DIACRITIC_MAP[chr(low)] = ascii_char
    DIACRITIC_MAP[chr(up)] = ascii_char.upper()

ROOT = Path(__file__).resolve().parent.parent
EXTENSIONS = {".py", ".md", ".sql", ".yml", ".yaml", ".xml", ".txt", ".bat", ".sh", ".cfg", ".ini", ".toml"}
EXCLUDE_DIRS = {".claude", ".pytest_cache", ".git", "__pycache__", "data", "logs", "node_modules", ".venv", "venv"}


def strip(text: str) -> str:
    return "".join(DIACRITIC_MAP.get(ch, ch) for ch in text)


def main() -> int:
    changed = 0
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in EXTENSIONS:
            continue
        if any(part in EXCLUDE_DIRS for part in path.relative_to(ROOT).parts):
            continue
        try:
            original = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        scrubbed = strip(original)
        if scrubbed != original:
            path.write_text(scrubbed, encoding="utf-8")
            changed += 1
            print(f"  rewrote {path.relative_to(ROOT)}")
    print(f"done: {changed} files updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
