from __future__ import annotations

from unittest.mock import MagicMock, patch

from lumi_print_agent import discover


def _one_host_net(host: str):
    net = MagicMock()
    net.hosts.return_value = [host]
    return net


def test_scan_subnet_enriches_identity():
    ident = {
        "manufacturer": "EPSON",
        "model": "TM-T88VII",
        "serial": "X9XL033135",
        "firmware": "",
        "mac": "dc:cd:2f:18:18:cb",
        "label": "EPSON TM-T88VII",
    }
    with patch("lumi_print_agent.discover.socket.create_connection") as conn:
        conn.return_value.__enter__.return_value = True
        with patch("lumi_print_agent.discover.ipaddress.ip_network", return_value=_one_host_net("192.168.1.237")):
            with patch("lumi_print_agent.discover.identify_escpos", return_value=ident):
                found = discover.scan_subnet("192.168.1.0/24", identify=True)
    assert len(found) == 1
    assert found[0]["host"] == "192.168.1.237"
    assert found[0]["manufacturer"] == "EPSON"
    assert found[0]["model"] == "TM-T88VII"
    assert found[0]["label"] == "EPSON TM-T88VII"


def test_scan_subnet_can_skip_identify():
    with patch("lumi_print_agent.discover.socket.create_connection") as conn:
        conn.return_value.__enter__.return_value = True
        with patch("lumi_print_agent.discover.ipaddress.ip_network", return_value=_one_host_net("10.0.0.8")):
            found = discover.scan_subnet("10.0.0.0/24", identify=False)
    assert found[0]["host"] == "10.0.0.8"
    assert found[0]["manufacturer"] == ""
