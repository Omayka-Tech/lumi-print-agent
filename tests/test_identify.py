from __future__ import annotations

from lumi_print_agent.identify import (
    brand_from_mac,
    format_identity,
    identify_escpos,
    parse_gs_i_string,
    printer_label,
    split_cups_description,
)


def test_parse_gs_i_string_strips_header_and_nul():
    assert parse_gs_i_string(b"_EPSON\x00") == "EPSON"
    assert parse_gs_i_string(b"_TM-T88VII\x00") == "TM-T88VII"
    assert parse_gs_i_string(b"_1.00.41 ESC/POS\x00") == "1.00.41 ESC/POS"
    assert parse_gs_i_string(b"") == ""


def test_format_identity_avoids_duplicating_brand():
    assert format_identity({"manufacturer": "EPSON", "model": "TM-T88VII"}) == "EPSON TM-T88VII"
    assert format_identity({"manufacturer": "EPSON", "model": "EPSON TM-T88VII"}) == "EPSON TM-T88VII"
    assert format_identity({"manufacturer": "FTX", "model": "TDR080UE"}) == "FTX TDR080UE"
    assert format_identity({"manufacturer": "", "model": ""}) == ""


def test_printer_label_includes_endpoint():
    assert printer_label({"manufacturer": "EPSON", "model": "TM-T88VII"}, "192.168.1.237") == (
        "EPSON TM-T88VII  —  192.168.1.237:9100"
    )
    assert printer_label({}, "192.168.1.215", 9100) == "192.168.1.215:9100"


def test_brand_from_public_oui():
    assert brand_from_mac("dc:cd:2f:18:18:cb") == "EPSON"
    assert brand_from_mac("6C-C1-47-5A-D0-19") == "HPRT"
    assert brand_from_mac("aa:bb:cc:dd:ee:ff") == ""


def test_split_cups_description():
    assert split_cups_description("EPSON TM-T88VII") == ("EPSON", "TM-T88VII")
    assert split_cups_description("EPSON_TM_T88VII") == ("EPSON", "TM T88VII")
    assert split_cups_description("Samsung ML-2160 Series") == ("Samsung", "ML-2160 Series")
    assert split_cups_description("Office_Printer") == ("", "Office Printer")


class _SeqSock:
    def __init__(self):
        self.last = b""

    def sendall(self, data):
        self.last = data

    def recv(self, _n):
        mapping = {
            b"\x1dI\x42": b"_EPSON\x00",
            b"\x1dI\x43": b"_TM-T88VII\x00",
            b"\x1dI\x44": b"_X9XL033135\x00",
            b"\x1dI\x41": b"_1.00\x00",
        }
        return mapping.get(self.last, b"")

    def settimeout(self, _t):
        return None

    def close(self):
        return None


def test_read_gs_i_fields_reuses_one_socket(monkeypatch):
    sock = _SeqSock()
    monkeypatch.setattr(
        "lumi_print_agent.identify.socket.create_connection",
        lambda *_a, **_k: sock,
    )
    from lumi_print_agent.identify import _read_gs_i_fields

    fields = _read_gs_i_fields("192.168.1.237", 9100, 0.2)
    assert fields["manufacturer"] == "EPSON"
    assert fields["model"] == "TM-T88VII"
    assert fields["serial"] == "X9XL033135"


def test_identify_escpos_reads_gs_i(monkeypatch):
    fields = {
        "manufacturer": "EPSON",
        "model": "TM-T88VII",
        "serial": "X9XL033135",
        "firmware": "1.00",
    }
    monkeypatch.setattr("lumi_print_agent.identify.lookup_mac", lambda _host: "dc:cd:2f:18:18:cb")
    monkeypatch.setattr("lumi_print_agent.identify._read_gs_i_fields", lambda *_a, **_k: fields)
    ident = identify_escpos("192.168.1.237")
    assert ident["manufacturer"] == "EPSON"
    assert ident["model"] == "TM-T88VII"
    assert ident["serial"] == "X9XL033135"
    assert ident["label"] == "EPSON TM-T88VII"
    assert ident["mac"] == "dc:cd:2f:18:18:cb"


def test_identify_falls_back_to_oui_when_gs_i_empty(monkeypatch):
    monkeypatch.setattr("lumi_print_agent.identify.lookup_mac", lambda _host: "6c:c1:47:5a:d0:19")
    monkeypatch.setattr(
        "lumi_print_agent.identify._read_gs_i_fields",
        lambda *_a, **_k: {"manufacturer": "", "model": "", "serial": "", "firmware": ""},
    )
    ident = identify_escpos("192.168.1.215")
    assert ident["manufacturer"] == "HPRT"
    assert ident["label"] == "HPRT"
