# scripts/validate_synthesis_note.py
import re, sys
from pathlib import Path
text = Path("e156-submission/synthesis-methods-note.md").read_text(encoding="utf-8")
clean = re.sub(r"<!--.*?-->", "", text, flags=re.S).strip()
words = clean.split()
print(f"words = {len(words)}")
assert len(words) <= 400, f"expected <=400 words, got {len(words)}"
for token in ("{{","}}"):
    assert token not in clean, f"unfilled placeholder {token!r}"
print("Synthesis methods note OK")
