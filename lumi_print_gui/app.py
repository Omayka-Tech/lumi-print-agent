"""Ventana mínima del agente: impresora local, test con corte, autostart."""

from __future__ import annotations

import os
import sys
import threading
from typing import Any, Dict, List, Optional

from lumi_print_agent.config import AgentConfig, load_config, save_config
from lumi_print_agent.discover import guess_cidr, scan_subnet
from lumi_print_agent.drivers import send_test_print
from lumi_print_agent.identify import identify_escpos, printer_label
from lumi_print_agent.local_api import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    ask_existing_to_open,
    make_server,
    probe_running,
)
from lumi_print_agent.paths import default_config_path, is_frozen, user_data_dir
from lumi_print_agent.state import RUNTIME
from lumi_print_agent.version import current_version

from . import autostart
from .install import needs_self_install, self_install_and_relaunch
from .macos_tk import reexec_with_tcl_tk8
from .icon import apply_window_icon
from .tray import TrayController


def _dispatch_headless(argv: List[str]) -> Optional[int]:
    headless = "--headless" in argv or os.environ.get("LUMI_PRINT_HEADLESS") == "1"
    if not headless:
        return None
    from lumi_print_agent.__main__ import main as headless_main

    cleaned = [a for a in argv if a != "--headless"]
    return headless_main(cleaned)


class PrintAgentApp:
    def __init__(self, start_hidden: bool = False) -> None:
        import tkinter as tk
        from tkinter import messagebox, ttk

        self.tk = tk
        self.messagebox = messagebox
        self.cfg_path = str(default_config_path())
        self.cfg: AgentConfig = load_config(self.cfg_path)
        self.server = None
        self.server_thread = None
        self.listen_ok = False
        self.busy = False
        self.tray: Optional[TrayController] = None
        self._exiting = False
        self._found_devices: List[Any] = []
        self.start_hidden = bool(start_hidden)

        self.root = tk.Tk()
        apply_window_icon(self.root)
        self.root.title("Lumi Print Agent")
        self.root.minsize(420, 520)
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
        self.version_var = tk.StringVar(value="v{}".format(current_version()))

        title_row = ttk.Frame(frm)
        title_row.pack(fill=tk.X, **pad)
        ttk.Label(
            title_row, text="Agente de impresión", font=("TkDefaultFont", 14, "bold")
        ).pack(side=tk.LEFT)
        ttk.Label(title_row, textvariable=self.version_var).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(title_row, text="↻", width=3, command=self._on_update).pack(side=tk.RIGHT)
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

        self.identity_var = tk.StringVar(value=self._identity_text())
        ttk.Label(box, textvariable=self.identity_var, wraplength=400).pack(anchor=tk.W, pady=(6, 0))

        btns = ttk.Frame(box)
        btns.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(btns, text="Probar impresión (con corte)", command=self._on_test).pack(
            side=tk.LEFT
        )

        discover = ttk.LabelFrame(frm, text="Descubrir en la LAN", padding=8)
        discover.pack(fill=tk.BOTH, expand=True, **pad)
        cidr_row = ttk.Frame(discover)
        cidr_row.pack(fill=tk.X)
        ttk.Label(cidr_row, text="LAN (CIDR)").pack(side=tk.LEFT)
        ttk.Entry(cidr_row, textvariable=self.cidr_var, width=18).pack(side=tk.LEFT, padx=6)
        ttk.Button(cidr_row, text="Descubrir LAN", command=self._on_discover).pack(side=tk.LEFT)
        ttk.Label(
            discover,
            text="Elegí un resultado (marca y modelo si la ticketera responde).",
            wraplength=400,
        ).pack(anchor=tk.W, pady=(6, 0))
        self.found = tk.Listbox(discover, height=5)
        self.found.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        self.found.bind("<<ListboxSelect>>", self._on_select_found)
        ttk.Button(discover, text="Guardar", command=self._on_save).pack(anchor=tk.W, pady=(8, 0))

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
        self.root.after(700, self._identify_current)

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
        self.tray = TrayController(
            self._show_window,
            self._on_test,
            self._quit,
            on_update=self._on_update,
        )
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
        self._identify_current()

    def _identity_text(self) -> str:
        label = self.cfg.printer.label()
        if label:
            return label
        if self.cfg.printer.host:
            return "Ticketera en {}:{} (sin identificar)".format(
                self.cfg.printer.host, self.cfg.printer.port
            )
        return "Sin impresora identificada"

    def _apply_identity(self, ident: Dict[str, Any]) -> None:
        self.cfg.printer.manufacturer = str(ident.get("manufacturer") or "")
        self.cfg.printer.model = str(ident.get("model") or "")
        self.cfg.printer.serial = str(ident.get("serial") or "")
        self.identity_var.set(self._identity_text())

    def _on_select_found(self, _evt: Any = None) -> None:
        sel = self.found.curselection()
        if not sel:
            return
        idx = int(sel[0])
        if idx < 0 or idx >= len(self._found_devices):
            return
        item = self._found_devices[idx]
        self.printer_var.set(str(item.get("host") or "").strip())
        self.port_var.set(str(item.get("port") or 9100))
        self.cfg.printer.host = self.printer_var.get()
        try:
            self.cfg.printer.port = int(self.port_var.get() or "9100")
        except ValueError:
            self.cfg.printer.port = 9100
        self._apply_identity(item)

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
        self._found_devices = list(devices or [])
        if err:
            self.status_var.set("Error al descubrir: {}".format(err))
            return
        if not devices:
            self.status_var.set("Nada en {} :9100".format(cidr))
            return
        for item in devices:
            self.found.insert(
                self.tk.END,
                printer_label(item, item.get("host") or "", int(item.get("port") or 9100)),
            )
        named = sum(1 for item in devices if item.get("manufacturer") or item.get("model"))
        summary = "Encontradas {} impresora(s)".format(len(devices))
        if named:
            summary += ", {} identificada(s)".format(named)
        self.status_var.set(summary)
        if self.listen_ok:
            self.status_var.set("Escuchando :{} — {}".format(self.cfg.local_api_port, summary.lower()))

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
        dest = printer_label(
            {
                "manufacturer": self.cfg.printer.manufacturer,
                "model": self.cfg.printer.model,
            },
            self.cfg.printer.host,
            self.cfg.printer.port,
        )
        self.last_var.set("Prueba enviada (con corte) a {}".format(dest))

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

    def _on_update(self) -> None:
        if self.busy:
            return
        self.busy = True
        self.last_var.set("Buscando actualización…")

        def work() -> None:
            err = ""
            info = None
            try:
                from lumi_print_agent.update import check_for_update

                info = check_for_update()
            except Exception as exc:
                err = str(exc)
            self.root.after(0, lambda: self._update_check_done(info, err))

        threading.Thread(target=work, daemon=True).start()

    def _update_check_done(self, info: Any, err: str) -> None:
        self.busy = False
        if err:
            self.last_var.set("No se pudo consultar updates: {}".format(err))
            self.messagebox.showerror("Actualización", err)
            return
        if info is None:
            self.last_var.set("No hay release publicado para esta plataforma.")
            self.messagebox.showinfo(
                "Actualización",
                "No hay un paquete publicado para esta plataforma.",
            )
            return
        current = current_version()
        if not info.update_available:
            self.last_var.set("Ya estás en v{}.".format(current))
            self.messagebox.showinfo(
                "Actualización",
                "Esta versión v{} ya es la última (v{}).".format(current, info.version),
            )
            return
        notes = (info.notes or "").strip()
        question = (
            "Hay una versión nueva v{}.\n"
            "Se descarga desde {}, se reemplazan los archivos y el agente "
            "vuelve a abrir en la bandeja."
        ).format(info.version, info.source)
        if notes:
            question = "{}\n\n{}".format(question, notes[:500])
        if not self.messagebox.askyesno("Actualización", question):
            self.last_var.set("Actualización cancelada.")
            return
        self.busy = True
        self.last_var.set("Descargando v{}…".format(info.version))

        def work() -> None:
            apply_err = ""
            try:
                from lumi_print_agent.update import apply_extracted_update, download_and_extract

                tree = download_and_extract(info)
                apply_extracted_update(tree, relaunch=True, hidden=True)
            except Exception as exc:
                apply_err = str(exc)
            self.root.after(0, lambda: self._update_apply_done(apply_err, info.version))

        threading.Thread(target=work, daemon=True).start()

    def _update_apply_done(self, err: str, version: str) -> None:
        self.busy = False
        if err:
            self.last_var.set("Error al actualizar: {}".format(err))
            self.messagebox.showerror("Actualización", err)
            return
        self.last_var.set("Actualizado a v{}. Reiniciando…".format(version))
        self.root.after(400, self._quit_silent)

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
            ident = self.cfg.printer.label()
            if ident and printer:
                extra = "{} ({})".format(ident, printer)
            elif printer:
                extra = "impresora {}".format(printer)
            else:
                extra = "sin impresora elegida"
            self.status_var.set("Escuchando :{} — {}".format(self.cfg.local_api_port, extra))
        self.root.after(1000, self._poll_status)

    def _identify_current(self) -> None:
        host = self.printer_var.get().strip() or self.cfg.printer.host
        if not host or self.busy:
            return

        def work() -> None:
            try:
                ident = identify_escpos(host, int(self.cfg.printer.port or 9100))
            except Exception:
                ident = {}
            self.root.after(0, lambda: self._identify_done(host, ident))

        threading.Thread(target=work, daemon=True).start()

    def _identify_done(self, host: str, ident: Dict[str, Any]) -> None:
        if host != (self.printer_var.get().strip() or self.cfg.printer.host):
            return
        if ident.get("manufacturer") or ident.get("model"):
            self._apply_identity(ident)
            save_config(self.cfg, self.cfg_path)

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
        if self.start_hidden:
            # Servicio de bandeja: no mostrar la ventana al iniciar sesión.
            self.root.withdraw()
        self.root.mainloop()
        return 0


def _gui_import_error_hint(exc: BaseException) -> str:
    text = str(exc)
    lines = ["No se pudo abrir la GUI (tkinter): {}".format(text), ""]
    if "libtk" in text or "_tkinter" in text or "tkinter" in text.lower():
        if sys.platform == "darwin":
            lines.extend(
                [
                    "En macOS, pyenv suele quedar ligado a Tcl/Tk 8.6 y Homebrew ya instala 9.x.",
                    "Opción A — Tcl/Tk 8.6 junto al pyenv actual:",
                    "  brew install tcl-tk@8",
                    '  export DYLD_FALLBACK_LIBRARY_PATH="$(brew --prefix tcl-tk@8)/lib${DYLD_FALLBACK_LIBRARY_PATH:+:$DYLD_FALLBACK_LIBRARY_PATH}"',
                    "  python -m lumi_print_gui",
                    "",
                    "Opción B — venv con Python de Homebrew (Tk incluido):",
                    "  brew install python@3.13 python-tk@3.13",
                    "  /opt/homebrew/bin/python3.13 -m venv .venv --clear",
                    '  source .venv/bin/activate && pip install -e ".[gui,dev]"',
                    "",
                    "El tubo headless no necesita Tk: python -m lumi_print_agent --no-poll",
                ]
            )
        else:
            lines.append("Instalá el paquete tkinter de tu distro (p.ej. python3-tk) e intentá de nuevo.")
    return "\n".join(lines) + "\n"


def _wants_hidden(args: List[str]) -> bool:
    if "--hidden" in args or "--tray" in args:
        return True
    if os.environ.get("LUMI_PRINT_HIDDEN") == "1":
        return True
    # Copia instalada: comportamiento de servicio (bandeja cerca del reloj).
    if is_frozen() and autostart.is_installed_copy() and "--show" not in args:
        return True
    return False


def main(argv: Optional[List[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    dispatched = _dispatch_headless(args)
    if dispatched is not None:
        return dispatched
    if "--install" in args or needs_self_install():
        return self_install_and_relaunch()
    reexec_with_tcl_tk8(args)
    try:
        app = PrintAgentApp(start_hidden=_wants_hidden(args))
    except Exception as exc:
        sys.stderr.write(_gui_import_error_hint(exc))
        return 1
    return app.run()
