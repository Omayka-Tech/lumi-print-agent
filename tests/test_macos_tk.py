from __future__ import annotations

import os

from lumi_print_gui.macos_tk import tcl_tk8_lib_dirs


def test_tcl_tk8_lib_dirs_only_returns_real_kegs():
    for path in tcl_tk8_lib_dirs():
        assert os.path.isfile(os.path.join(path, "libtk8.6.dylib"))
