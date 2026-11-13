"""Icono de bandeja: Abrir / Actualizar / Probar / Salir."""

from __future__ import annotations

from typing import Callable, Optional

from .icon import make_icon_image


class TrayController:
    def __init__(
        self,
        on_open: Callable[[], None],
        on_test: Callable[[], None],
        on_exit: Callable[[], None],
        on_update: Optional[Callable[[], None]] = None,
    ) -> None:
        self.on_open = on_open
        self.on_test = on_test
        self.on_exit = on_exit
        self.on_update = on_update
        self._icon = None

    def start(self) -> bool:
        try:
            import pystray
        except Exception:
            return False
        items = [
            pystray.MenuItem("Abrir", lambda _icon, _item: self.on_open(), default=True),
        ]
        if self.on_update is not None:
            items.append(
                pystray.MenuItem("Actualizar…", lambda _icon, _item: self.on_update())
            )
        items.extend(
            [
                pystray.MenuItem("Probar", lambda _icon, _item: self.on_test()),
                pystray.MenuItem("Salir", lambda _icon, _item: self.on_exit()),
            ]
        )
        menu = pystray.Menu(*items)
        self._icon = pystray.Icon(
            "lumi-print-agent",
            make_icon_image(),
            "Lumi Print Agent",
            menu,
        )
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
