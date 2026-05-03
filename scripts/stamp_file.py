"""OpenTimestamps stamper — calendar HTTP API only.

Why: the ots CLI on Windows + Python 3.13 fails to load libeay32 (legacy
OpenSSL) via python-bitcoinlib's ctypes path. Direct calendar HTTP works
without that dep.

Usage:
    python scripts/stamp_file.py <path> [<path> ...]

Writes <path>.ots beside each input file. The .ots file is an
OTS-compatible serialisation of the file's sha256 digest extended with
PendingAttestation operations from each calendar. Bitcoin confirmation
follows asynchronously (hours-to-day); the receipt is committable
immediately.
"""

from __future__ import annotations

import hashlib
import io
import sys
from pathlib import Path

from opentimestamps.core.notary import PendingAttestation
from opentimestamps.core.op import OpAppend, OpSHA256
from opentimestamps.core.serialize import BytesDeserializationContext, StreamSerializationContext
from opentimestamps.core.timestamp import DetachedTimestampFile, Timestamp

import urllib.request


CALENDARS = [
    "https://a.pool.opentimestamps.org",
    "https://b.pool.opentimestamps.org",
    "https://finney.calendar.eternitywall.com",
]


def submit_to_calendar(calendar_url: str, digest: bytes) -> bytes:
    """POST a 32-byte sha256 digest to a calendar's /digest endpoint.

    Returns the calendar's binary response (a serialised Timestamp).
    """
    req = urllib.request.Request(
        f"{calendar_url}/digest",
        data=digest,
        headers={
            "Accept": "application/vnd.opentimestamps.v1",
            "User-Agent": "pactr-hiddenness-atlas-stamper/0.0.1",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def make_merkle_tip_timestamp(file_digest: bytes) -> Timestamp:
    """Produce a Timestamp anchored at sha256(file_digest || nonce_per_calendar).

    Each calendar gets its own nonce-extended branch so that the calendar
    sees a unique digest (privacy preserving) and so multiple calendars
    can each anchor independently to Bitcoin.
    """
    import secrets

    root_ts = Timestamp(file_digest)
    for cal in CALENDARS:
        nonce = secrets.token_bytes(16)
        nonced = root_ts.ops.add(OpAppend(nonce))
        hashed = nonced.ops.add(OpSHA256())
        try:
            cal_response = submit_to_calendar(cal, hashed.msg)
        except Exception as exc:
            print(f"  ! {cal} failed: {exc}", file=sys.stderr)
            continue
        ctx = BytesDeserializationContext(cal_response)
        cal_ts = Timestamp.deserialize(ctx, hashed.msg)
        # Replace the empty Timestamp at this branch with the calendar's response
        for op, ts in cal_ts.ops.items():
            hashed.ops[op] = ts
        for att in cal_ts.attestations:
            hashed.attestations.add(att)
        print(f"  + {cal} OK")
    return root_ts


def stamp(path: Path) -> Path:
    if not path.is_file():
        raise FileNotFoundError(f"not a file: {path}")
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).digest()
    print(f"stamping {path}")
    print(f"  sha256 = {digest.hex()}")
    ts = make_merkle_tip_timestamp(digest)
    if not any(True for _ in _walk_attestations(ts)):
        raise RuntimeError(
            f"no calendar accepted the stamp request for {path} — refuse to write empty .ots"
        )
    detached = DetachedTimestampFile(file_hash_op=OpSHA256(), timestamp=ts)
    out = path.with_suffix(path.suffix + ".ots")
    with out.open("wb") as fh:
        ctx = StreamSerializationContext(fh)
        detached.serialize(ctx)
    print(f"  wrote {out}")
    return out


def _walk_attestations(ts: Timestamp):
    yield from ts.attestations
    for sub in ts.ops.values():
        yield from _walk_attestations(sub)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    for arg in argv[1:]:
        stamp(Path(arg))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
