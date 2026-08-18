from __future__ import annotations

from lumi_print_agent.test_ticket import GS_CUT_FULL, build_test_ticket


def test_ticket_includes_full_cut():
    raw = build_test_ticket()
    assert raw.startswith(b"\x1b@")
    assert GS_CUT_FULL in raw
    assert raw.endswith(GS_CUT_FULL)
    assert b"Prueba ESC/POS OK" in raw
