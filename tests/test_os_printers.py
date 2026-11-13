"""Tests de listado de impresoras OS/LAN del agente."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from lumi_print_agent import os_printers


def test_list_cups_printers_parses_lpstat():
    lp_p = MagicMock(return_value=MagicMock(returncode=0, stdout="printer Office_Printer is idle.\nprinter Thermal is idle.\n"))
    lp_d = MagicMock(return_value=MagicMock(returncode=0, stdout="system default destination: Office_Printer\n"))

    def fake_run(cmd, **kwargs):
        args = cmd[1:]
        if args == ["-p"]:
            return lp_p.return_value
        if args == ["-d"]:
            return lp_d.return_value
        return MagicMock(returncode=0, stdout="")

    with patch.object(os_printers.subprocess, "run", side_effect=fake_run):
        printers = os_printers.list_cups_printers()

    assert len(printers) == 2
    assert printers[0]["name"] == "Office_Printer"
    assert printers[0]["is_default"] is True
    assert printers[0]["driver"] == "cups_spooler"
    assert printers[1]["is_default"] is False
    assert "manufacturer" in printers[0]
    assert "label" in printers[0]


def test_list_cups_printers_missing_lpstat():
    with patch.object(os_printers.subprocess, "run", side_effect=FileNotFoundError):
        assert os_printers.list_cups_printers() == []


def test_list_cups_printers_reads_description_and_socket_uri():
    lp_p = MagicMock(returncode=0, stdout="printer EPSON_TM_T88VII is idle.\n")
    lp_d = MagicMock(returncode=0, stdout="system default destination: EPSON_TM_T88VII\n")
    lp_l = MagicMock(
        returncode=0,
        stdout=(
            "printer EPSON_TM_T88VII is idle.\n"
            "\tDescription: EPSON TM-T88VII\n"
        ),
    )
    lp_v = MagicMock(returncode=0, stdout="device for EPSON_TM_T88VII: socket://192.168.1.237:9100\n")

    def fake_run(cmd, **kwargs):
        args = cmd[1:]
        if args == ["-p"]:
            return lp_p
        if args == ["-d"]:
            return lp_d
        if args == ["-l", "-p"]:
            return lp_l
        if args == ["-v"]:
            return lp_v
        raise AssertionError(cmd)

    with patch.object(os_printers.subprocess, "run", side_effect=fake_run):
        printers = os_printers.list_cups_printers()

    assert printers[0]["name"] == "EPSON_TM_T88VII"
    assert printers[0]["manufacturer"] == "EPSON"
    assert printers[0]["model"] == "TM-T88VII"
    assert "192.168.1.237" in printers[0]["label"]


def test_list_local_printers_merges_cups_and_network():
    cups = [{"id": "cups-X", "name": "X", "driver": "cups_spooler", "connection_detail": {"queue": "X"}}]
    net = [
        {
            "host": "192.168.1.10",
            "port": 9100,
            "driver": "escpos_network",
            "printer_type": "thermal",
            "manufacturer": "EPSON",
            "model": "TM-T88VII",
            "label": "EPSON TM-T88VII",
        }
    ]
    with patch.object(os_printers, "list_cups_printers", return_value=cups):
        with patch.object(os_printers, "scan_subnet", return_value=net):
            merged = os_printers.list_local_printers("192.168.1.0/24")
    assert len(merged) == 2
    assert merged[0]["id"] == "cups-X"
    assert merged[1]["id"] == "net-192.168.1.10-9100"
    assert merged[1]["manufacturer"] == "EPSON"
    assert merged[1]["model"] == "TM-T88VII"
    assert "TM-T88VII" in merged[1]["name"]
