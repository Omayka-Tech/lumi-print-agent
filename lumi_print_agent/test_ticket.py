"""Ticket ESC/POS de prueba con corte de papel."""

from __future__ import annotations

# ESC/POS: ESC @ init, ESC a center, ESC E bold, GS V 0 full cut (Epson TM-T88).
ESC_INIT = b"\x1b@"
ESC_ALIGN_CENTER = b"\x1b\x61\x01"
ESC_ALIGN_LEFT = b"\x1b\x61\x00"
ESC_BOLD_ON = b"\x1bE\x01"
ESC_BOLD_OFF = b"\x1bE\x00"
GS_CUT_FULL = b"\x1dV\x00"


def build_test_ticket(label: str = "LUMI PRINT AGENT") -> bytes:
    body = (
        "{}\n"
        "Prueba ESC/POS OK\n"
        "Test print con corte\n"
        "------------------------\n"
    ).format(label).encode("utf-8")
    return (
        ESC_INIT
        + ESC_ALIGN_CENTER
        + ESC_BOLD_ON
        + body
        + ESC_BOLD_OFF
        + ESC_ALIGN_LEFT
        + b"\n\n\n"
        + GS_CUT_FULL
    )
