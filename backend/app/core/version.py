from __future__ import annotations

import os


def get_version_info() -> dict:
    """Return build/version metadata.

    Values are intentionally best-effort and may be empty.
    """

    return {
        "app": "agentpress",
        "version": os.getenv("AGENTPRESS_VERSION", "0.1.0"),
        "build_sha": os.getenv("AGENTPRESS_BUILD_SHA", ""),
        "build_time": os.getenv("AGENTPRESS_BUILD_TIME", ""),
    }
