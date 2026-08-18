"""Ventana mínima del agente: impresora local, test con corte, autostart."""

from __future__ import annotations

import os
import sys
import threading
from typing import Any, List, Optional

from lumi_print_agent.config import AgentConfig, load_config, save_config
from lumi_print_agent.discover import guess_cidr, scan_subnet
from lumi_print_agent.drivers import send_test_print
from lumi_print_agent.local_api import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    ask_existing_to_open,
    make_server,
    probe_running,
)
from lumi_print_agent.paths import default_config_path, is_frozen, user_data_dir
from lumi_print_agent.state import RUNTIME

from . import autostart
from .install import needs_self_install, self_install_and_relaunch
from .tray import TrayController


def _dispatch_headless(argv: List[str]) -> Optional[int]:
    headless = "--headless" in argv or os.environ.get("LUMI_PRINT_HEADLESS") == "1"
    if not headless:
        return None
    from lumi_print_agent.__main__ import main as headless_main

    cleaned = [a for a in argv if a != "--headless"]
    return headless_main(cleaned)


class PrintAgentApp:
    def __init__(self) -> None:
        import tkinter as tk
        from tkinter import ttk

        self.tk = tk
        self.cfg_path = str(default_config_path())
        self.cfg: AgentConfig = load_config(self.cfg_path)
        self.server = None
        self.server_thread = None
        self.listen_ok = False
        self.busy = False
        self.tray: Optional[TrayController] = None
        self._exiting = False

        self.root = tk.Tk()
        self.root.title("Lumi Print Agent")
        self.root.minsize(420, 460)
        self.root.protocol("WM_DELETE_WINDOW", self._hide_to_tray)

        pad = {"padx": 10, "pady": 4}
        frm = ttk.Frame(self.root, padding=12)
        frm.pack(fill=tk.BOTH, expand=True)

        self.status_var = tk.StringVar(value="Iniciando…")
        self.printer_var = tk.StringVar(value=self.cfg.printer.host)
        self.port_var = tk.StringVar(value=str(self.cfg.printer.port))
        self.last_var = tk.StringVar(value="Último trabajo: —")
        self.install_var = tk.StringVar(value="")
        self.autostart_var = tk.BooleanVar(value=self.cfg.autostart or autostart.is_enabled())
        self.cidr_var = tk.StringVar(value=self.cfg.printer.cidr or guess_cidr())

        ttk.Label(frm, text="Agente de impresión", font=("TkDefaultFont", 14, "bold")).pack(
            anchor=tk.W, **pad
        )
        self.status_lbl = ttk.Label(frm, textvariable=self.status_var)
        self.status_lbl.pack(anchor=tk.W, **pad)
        ttk.Label(frm, textvariable=self.last_var, wraplength=400).pack(anchor=tk.W, **pad)

        box = ttk.LabelFrame(frm, text="Impresora térmica", padding=8)
        box.pack(fill=tk.X, **pad)
        row = ttk.Frame(box)
        row.pack(fill=tk.X)
        ttk.Label(row, text="Host").pack(side=tk.LEFT)
        ttk.Entry(row, textvariable=self.printer_var, width=22).pack(side=tk.LEFT, padx=6)
        ttk.Label(row, text="Puerto").pack(side=tk.LEFT)
        ttk.Entry(row, textvariable=self.port_var, width=6).pack(side=tk.LEFT, padx=6)

        cidr_row = ttk.Frame(box)
        cidr_row.pack(fill=tk.X, pady=(6, 0))
        ttk.Label(cidr_row, text="LAN (CIDR)").pack(side=tk.LEFT)
        ttk.Entry(cidr_row, textvariable=self.cidr_var, width=18).pack(side=tk.LEFT, padx=6)
        ttk.Button(cidr_row, text="Descubrir LAN", command=self._on_discover).pack(side=tk.LEFT)

        self.found = tk.Listbox(box, height=5)
        self.found.pack(fill=tk.X, pady=6)
        self.found.bind("<<ListboxSelect>>", self._on_select_found)

        btns = ttk.Frame(box)
        btns.pack(fill=tk.X)
        ttk.Button(btns, text="Probar impresión (con corte)", command=self._on_test).pack(
            side=tk.LEFT
        )
        ttk.Button(btns, text="Guardar", command=self._on_save).pack(side=tk.LEFT, padx=6)

        auto = ttk.LabelFrame(frm, text="Inicio con el sistema", padding=8)
        auto.pack(fill=tk.X, **pad)
        self.auto_chk = ttk.Checkbutton(
            auto,
            text="Arrancar al iniciar sesión",
            variable=self.autostart_var,
            command=self._on_autostart_toggle,
        )
        self.auto_chk.pack(anchor=tk.W)
        ttk.Label(auto, textvariable=self.install_var, wraplength=400).pack(anchor=tk.W)
        self.install_btn = ttk.Button(auto, text="Instalar en esta cuenta", command=self._on_install)
        self.install_btn.pack(anchor=tk.W, pady=(4, 0))

        ttk.Label(
            frm,
            text="Chrome envía el ticket a http://127.0.0.1:{}/print-direct".format(
                self.cfg.local_api_port or DEFAULT_PORT
            ),
            wraplength=400,
        ).pack(anchor=tk.W, pady=(8, 0))

        self._refresh_install_ui()
        self.root.after(400, self._poll_status)

    def start_api(self) -> None:
        host = self.cfg.local_api_host or DEFAULT_HOST
        port = int(self.cfg.local_api_port or DEFAULT_PORT)
        probe_host = DEFAULT_HOST if host in ("0.0.0.0", "::") else host
        if probe_running(probe_host, port):
            ask_existing_to_open(probe_host, port)
            self.status_var.set("Ya hay un agente en :{}. Cerrando esta copia.".format(port))
            self.root.after(600, self._quit_silent)
            return
        try:
            self.server = make_server(host=host, port=port, config_path=self.cfg_path)
        except OSError:
            self.status_var.set("Puerto :{} ocupado — el agente ya está en ejecución.".format(port))
            self.root.after(800, self._quit_silent)
            return
        RUNTIME.open_ui = lambda: self.root.after(0, self._show_window)
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()
        self.listen_ok = True
        self.status_var.set("Escuchando :{}".format(port))

    def start_tray(self) -> None:
        self.tray = TrayController(self._show_window, self._on_test, self._quit)
        if not self.tray.start():
            self.tray = None

    def _refresh_install_ui(self) -> None:
        frozen = is_frozen()
        installed = autostart.is_installed_copy()
        if not frozen:
            self.install_var.set("Modo desarrollo (sin self-install). Config: {}".format(self.cfg_path))
            self.install_btn.state(["disabled"])
            return
        if installed:
            self.install_var.set("Instalado en {}".format(user_data_dir()))
            self.install_btn.state(["disabled"])
        else:
            self.install_var.set(
                "Esta copia no está en la carpeta de usuario. Instalá para poder usar autostart."
            )
            self.install_btn.state(["!disabled"])
        if not installed and frozen:
            self.auto_chk.state(["disabled"])
        else:
            self.auto_chk.state(["!disabled"])

    def _hide_to_tray(self) -> None:
        if self.tray is not None:
            self.root.withdraw()
            return
        self._quit()

    def _show_window(self) -> None:
        self.root.deiconify()
        self.root.lift()
        try:
            self.root.focus_force()
        except Exception:
            pass

    def _read_printer(self) -> None:
        self.cfg.printer.host = self.printer_var.get().strip()
        try:
            self.cfg.printer.port = int(self.port_var.get().strip() or "9100")
        except ValueError:
            self.cfg.printer.port = 9100
            self.port_var.set("9100")
        self.cfg.printer.cidr = self.cidr_var.get().strip()

    def _on_save(self) -> None:
        self._read_printer()
        self.cfg.autostart = bool(self.autostart_var.get())
        save_config(self.cfg, self.cfg_path)
        self.last_var.set("Configuración guardada.")

    def _on_select_found(self, _evt: Any = None) -> None:
        sel = self.found.curselection()
        if not sel:
            return
        line = self.found.get(sel[0])
        if ":" not in line:
            return
        host, port = line.rsplit(":", 1)
        self.printer_var.set(host.strip())
        self.port_var.set(port.strip())

    def _on_discover(self) -> None:
        if self.busy:
            return
        self.busy = True
        self.status_var.set("Buscando impresoras en la LAN…")
        cidr = self.cidr_var.get().strip() or guess_cidr()

        def work() -> None:
            try:
                devices = scan_subnet(cidr)
                err = ""
            except Exception as exc:
                devices = []
                err = str(exc)
            self.root.after(0, lambda: self._discover_done(devices, err, cidr))

        threading.Thread(target=work, daemon=True).start()

    def _discover_done(self, devices: List[Any], err: str, cidr: str) -> None:
        self.busy = False
        self.found.delete(0, self.tk.END)
        if err:
            self.status_var.set("Error al descubrir: {}".format(err))
            return
        if not devices:
            self.status_var.set("Nada en {} :9100".format(cidr))
            return
        for item in devices:
            self.found.insert(self.tk.END, "{}:{}".format(item["host"], item["port"]))
        self.status_var.set("Encontradas {} impresora(s)".format(len(devices)))
        if self.listen_ok:
            self.status_var.set(
                "Escuchando :{} — {} impresora(s)".format(self.cfg.local_api_port, len(devices))
            )

    def _on_test(self) -> None:
        if self.busy:
            return
        self._read_printer()
        if not self.cfg.printer.host:
            self.last_var.set("Elegí un host (descubrir LAN o escribir la IP).")
            return
        self.busy = True
        self.last_var.set("Enviando prueba con corte…")
        detail = self.cfg.connection_detail()
        driver = self.cfg.printer.driver_id or "escpos_network"

        def work() -> None:
            try:
                send_test_print(detail, driver)
                err = ""
            except Exception as exc:
                err = str(exc)
            self.root.after(0, lambda: self._test_done(err))

        threading.Thread(target=work, daemon=True).start()

    def _test_done(self, err: str) -> None:
        self.busy = False
        if err:
            RUNTIME.record(False, error=err)
            self.last_var.set("Error: {}".format(err))
            return
        RUNTIME.record(True, detail="test print con corte")
        save_config(self.cfg, self.cfg_path)
        self.last_var.set("Prueba enviada (con corte) a {}:{}".format(
            self.cfg.printer.host, self.cfg.printer.port
        ))

    def _on_autostart_toggle(self) -> None:
        if is_frozen() and not autostart.is_installed_copy():
            self.autostart_var.set(False)
            self.last_var.set("Instalá el agente en esta cuenta antes de activar autostart.")
            return
        enabled = bool(self.autostart_var.get())
        try:
            if enabled:
                autostart.enable()
            else:
                autostart.disable()
            self.cfg.autostart = enabled
            save_config(self.cfg, self.cfg_path)
            self.last_var.set("Autostart {}.".format("activado" if enabled else "desactivado"))
        except Exception as exc:
            self.autostart_var.set(not enabled)
            self.last_var.set("No se pudo cambiar autostart: {}".format(exc))

    def _on_install(self) -> None:
        if not is_frozen():
            return
        self.last_var.set("Copiando a {}…".format(user_data_dir()))
        self.root.after(100, self._do_install)

    def _do_install(self) -> None:
        self_install_and_relaunch()
        self._quit_silent()

    def _poll_status(self) -> None:
        if self._exiting:
            return
        snap = RUNTIME.snapshot()
        if snap.get("at"):
            if snap.get("ok"):
                text = "Último trabajo OK ({})".format(snap["at"])
                if snap.get("detail"):
                    text += " — {}".format(snap["detail"])
            else:
                text = "Último error ({}) — {}".format(snap["at"], snap.get("error") or "")
            if not self.busy:
                self.last_var.set(text)
        printer = self.printer_var.get().strip()
        if self.listen_ok:
            extra = "impresora {}".format(printer) if printer else "sin impresora elegida"
            self.status_var.set("Escuchando :{} — {}".format(self.cfg.local_api_port, extra))
        self.root.after(1000, self._poll_status)

    def _quit_silent(self) -> None:
        self._exiting = True
        if self.server is not None:
            try:
                self.server.shutdown()
            except Exception:
                pass
        if self.tray is not None:
            self.tray.stop()
        self.root.destroy()

    def _quit(self) -> None:
        self._quit_silent()

    def run(self) -> int:
        self.start_api()
        self.start_tray()
        self.root.mainloop()
        return 0


def main(argv: Optional[List[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    dispatched = _dispatch_headless(args)
    if dispatched is not None:
        return dispatched
    if "--install" in args or needs_self_install():
        return self_install_and_relaunch()
    try:
        app = PrintAgentApp()
    except Exception as exc:
        sys.stderr.write("No se pudo abrir la GUI (¿tkinter?): {}\n".format(exc))
        from lumi_print_agent.__main__ import main as headless_main

        return headless_main(args)
    return app.run()
