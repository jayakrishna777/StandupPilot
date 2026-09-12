"""The extension toolchain is declared before the production bridge is added."""

from __future__ import annotations

import json
from pathlib import Path


def test_extension_declares_node_toolchain_without_application_secrets():
    manifest = json.loads(
        (Path(__file__).parents[2] / "extension" / "package.json").read_text(encoding="utf-8")
    )

    assert manifest["private"] is True
    assert manifest["engines"]["node"].startswith(">=20")
    assert "test" in manifest["scripts"]
    assert "secret" not in (json.dumps(manifest).lower())
