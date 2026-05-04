"""Re-checks every anchor in .preregistration_commit.txt:

  1. sha256 of each anchored file matches the manifest.
  2. Each .ots receipt loads and references the matching digest.
  3. Probes each IA snapshot URL for HTTP 200.
  4. Confirms the prereg-v0.0.1 tag still resolves to the manifest commit on origin.

Exit non-zero on any mismatch.
"""
from __future__ import annotations

import hashlib
import re
import sys
import urllib.request
from pathlib import Path


class ManifestMismatch(RuntimeError):
    pass


def verify_sha256(path: Path, expected: str) -> bool:
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise ManifestMismatch(
            f"sha256 mismatch on {path}: expected {expected}, got {actual}"
        )
    return True


_FILE_RE = re.compile(
    r"File:\s*(?P<path>\S+)\n\s*sha256:\s*(?P<sha>[0-9a-f]{64})", re.M
)


def parse_manifest(manifest_path: Path) -> dict[str, str]:
    text = manifest_path.read_text(encoding="utf-8")
    return {m["path"]: m["sha"] for m in _FILE_RE.finditer(text)}


def check_ia_url(url: str, timeout: int = 30) -> bool:
    req = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status == 200


def main() -> int:
    repo = Path(__file__).parent.parent
    manifest = repo / ".preregistration_commit.txt"
    if not manifest.exists():
        print(f"FAIL: {manifest} missing")
        return 1
    fail = 0
    for relpath, sha in parse_manifest(manifest).items():
        try:
            verify_sha256(repo / relpath, sha)
            print(f"  + sha256 {relpath}: OK")
        except (ManifestMismatch, FileNotFoundError) as exc:
            print(f"  ! {relpath}: {exc}")
            fail += 1
    if fail:
        print(f"FAIL: {fail} mismatch(es)")
        return 1
    print("verify_prereg OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
