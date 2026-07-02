#!/usr/bin/env python3
"""Extract block definitions from a local Space Engineers install.

Usage::

    python scripts/extract_blockdata.py "C:/.../SpaceEngineers/Content/Data" \
        -o data/block_definitions.json

Parses every ``CubeBlocks*.sbc`` under the given directory and writes the
normalized dataset committed to the repo and seeded on migrate. Uses the same
parser as the server-side admin re-upload (``app.services.blockdata``).
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

# Allow running as a standalone script from the repo root.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.blockdata import parse_cubeblocks_xml  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Extract SE block definitions.")
    ap.add_argument("content_data_dir", help="Path to <SE install>/Content/Data")
    ap.add_argument("-o", "--output", default="data/block_definitions.json")
    args = ap.parse_args()

    pattern = os.path.join(args.content_data_dir, "**", "CubeBlocks*.sbc")
    files = glob.glob(pattern, recursive=True)
    if not files:
        print(f"No CubeBlocks*.sbc files found under {args.content_data_dir}", file=sys.stderr)
        return 1

    all_defs: dict[tuple[str, str], dict] = {}
    for path in sorted(files):
        with open(path, "rb") as f:
            for d in parse_cubeblocks_xml(f.read()):
                all_defs[(d.type_id, d.subtype_id)] = d.as_dict()

    blocks = sorted(all_defs.values(), key=lambda d: (d["type_id"], d["subtype_id"]))
    payload = {"source": "extracted", "blocks": blocks}
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(f"Wrote {len(blocks)} block definitions to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
