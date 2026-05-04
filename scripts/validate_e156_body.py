# scripts/validate_e156_body.py
import re, sys
from pathlib import Path
text = Path("e156-submission/body.md").read_text(encoding="utf-8")
# Strip HTML comments
clean = re.sub(r"<!--.*?-->", "", text, flags=re.S).strip()
sentences = [s for s in re.split(r"(?<=[.!?])\s+", clean) if s.strip()]
words = clean.split()
print(f"sentences = {len(sentences)}; words = {len(words)}")
assert len(sentences) == 7, f"expected 7 sentences, got {len(sentences)}"
assert len(words) <= 156, f"expected <=156 words, got {len(words)}"
# Refuse to validate if any placeholder remains
for token in ("{{","}}"):
    assert token not in clean, f"unfilled placeholder {token!r} in body"
print("E156 body OK")
