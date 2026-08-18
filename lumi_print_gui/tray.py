"""Icono de bandeja: Abrir / Probar / Salir."""

from __future__ import annotations

from typing import Callable

from .icon import make_icon_image


class TrayController:
    def __init__(
        self,
        on_open: Callable[[], None],
        on_test: Callable[[], None],
        on_exit: Callable[[], None],
    ) -> None:
        self.on_open = on_open
        self.on_test = on_test
        self.on_exit = on_exit
        self._icon = None

    def start(self) -> bool:
        try:
            import pystray
        except Exception:
            return False
        menu = pystray.Menu(
            pystray.MenuItem("Abrir", lambda _icon, _item: self.on_open(), default=True),
            pystray.MenuItem("Probar", lambda _icon, _item: self.on_test()),
            pystray.MenuItem("Salir", lambda _icon, _item: self.on_exit()),
        )
        self._icon = pystray.Icon("lumi-print-agent", make_icon_image(), "Lumi Print Agent", menu)
        run_detached = getattr(self._icon, "run_detached", None)
        if callable(run_detached):
            run_detached()
            return True
        # Fallback: hilo (Windows/Linux). En macOS puede no mostrar el icono.
        import threading

        threading.Thread(target=self._icon.run, daemon=True).start()
        return True

    def stop(self) -> None:
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception:
                pass
            self._icon = None
