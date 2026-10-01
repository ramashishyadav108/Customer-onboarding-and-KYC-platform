"""AC-07.9: the stubbed account creation performs no network I/O."""

import re
from pathlib import Path

import pytest

SOURCE = (
    Path(__file__).resolve().parents[2] / "src" / "onboardx" / "services" / "account_service.py"
)
NETWORK_MODULES = re.compile(
    r"^\s*(?:import|from)\s+(httpx|requests|urllib|socket|aiohttp|http\.client)\b", re.M
)


@pytest.mark.ac("AC-07.9")
def test_ac07_9_account_stub_imports_no_network_library() -> None:
    assert NETWORK_MODULES.findall(SOURCE.read_text(encoding="utf-8")) == []
