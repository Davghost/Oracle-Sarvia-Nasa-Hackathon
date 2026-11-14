"""Download the two GCOV scenes (before/during) into data/.  [NOT TESTED against the real API]

Run this in the Codespace (fast network), not on a slow home connection.
Needs: pip install asf_search
Credentials: Earthdata token in the EARTHDATA_TOKEN environment variable
(Codespaces secret). Never put it in the repo.

If the name search finds nothing, copy each scene's download URL from ASF Vertex
and use wget instead (see docs/download.md).
"""
import os
import sys
from pathlib import Path

import asf_search as asf

GRANULES = [
    "NISAR_L2_PR_GCOV_009_114_A_165_4005_DHDH_A_20260105T034232_20260105T034253_X05010_N_P_J_001",  # before, 2026-01-05
    "NISAR_L2_PR_GCOV_010_114_A_165_4005_DHDH_A_20260117T034232_20260117T034254_X05010_N_P_J_001",  # during, 2026-01-17
]
DEST = Path(__file__).resolve().parent.parent / "data"


def main() -> int:
    token = os.environ.get("EARTHDATA_TOKEN")
    if not token:
        print("EARTHDATA_TOKEN is not set.", file=sys.stderr)
        return 1
    DEST.mkdir(exist_ok=True)

    results = asf.granule_search(GRANULES)
    print(f"Found {len(results)} result(s) for {len(GRANULES)} requested granule(s).")
    for r in results:
        p = r.properties
        print(p.get("fileID"), p.get("url"), p.get("bytes"))
    if not results:
        print("Nothing found. Check the names or use the wget fallback.", file=sys.stderr)
        return 2

    session = asf.ASFSession()
    session.auth_with_token(token)
    results.download(path=str(DEST), session=session, processes=2)
    print("Done. Files in", DEST)
    return 0


if __name__ == "__main__":
    sys.exit(main())
