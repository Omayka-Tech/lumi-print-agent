# Lumi Print Agent

Agente local de impresión para [Lumi ERP](https://github.com/Omayka-Tech/lumi-erp). Una ventana, no un POS: habla con la ticketera (Epson TM-T88 y compatibles ESC/POS en `:9100`).

## Descargas

- **Canónico:** [https://downloads.lumi.com.py/](https://downloads.lumi.com.py/) — última build en [`/latest/`](https://downloads.lumi.com.py/latest/)
- **GitHub Releases:** [Omayka-Tech/lumi-print-agent/releases](https://github.com/Omayka-Tech/lumi-print-agent/releases)

Artefactos por tag `vX.Y.Z`:

| Archivo | Plataforma |
|---------|------------|
| `LumiPrintAgent-windows-x86_64-vX.Y.Z.zip` | Windows 7+ (x86/x64) |
| `LumiPrintAgent-macos-arm64-vX.Y.Z.tar.gz` | macOS 12+ (Apple Silicon) |
| `LumiPrintAgent-linux-x86_64-vX.Y.Z.tar.gz` | Linux x86_64 |
| `SHA256SUMS` | Checksums |

### Soporte

| Plataforma | Runtime soportado | Notas |
|------------|-------------------|--------|
| Windows | **7+** (x86/x64) | Build CI con CPython **3.8** en runner moderno; el runtime sigue siendo Win7+ |
| macOS | **12+** | Arm64 (Apple Silicon) |
| Linux | **x86_64** | glibc reciente (Ubuntu 22.04+) |
| Python | Solo builds desde fuente | 3.8+ (piso Win7); 3.10+ recomendado en macOS/Linux |

### Requisitos en caja

- Ticketera ESC/POS en red (`:9100`) o USB vía driver compatible.
- Chrome / POS web hablando con el agente en `http://127.0.0.1:17890` (sin API key en el modo default).
- Extraer el zip/tar → ejecutar el binario **una vez** → self-install a carpeta de usuario (ver abajo).

### Cómo liberar una versión

```bash
git tag v0.1.0
git push origin v0.1.0
```

Eso dispara `.github/workflows/release.yml`: build Win/macOS/Linux → GitHub Release + espejo en `downloads.lumi.com.py`.

---

Requiere **Windows 7+** / macOS / Linux. El POS desktop Tauri queda para cajas Win10+.

## Default (esta versión)

Chrome (sesión JWT) pide el ticket a Lumi, y el browser lo manda al agente:

`Chrome → Cloud → Chrome → POST http://127.0.0.1:17890/print-direct → impresora`

La GUI **no pide** URL de Lumi ni API key. El agente es un tubo local.

## Avanzado (después, mismo binario)

`Chrome → Cloud (encola PrintJob) → Agente poll → impresora`

El poll vive en el núcleo (`lumi_print_agent.agent`) y está **apagado**. No hay panel Avanzado en esta entrega.

## Instalación (sin MSI)

1. Bajá el zip/tar desde [downloads.lumi.com.py/latest/](https://downloads.lumi.com.py/latest/) (o GitHub Releases) y extraélo.
2. Abrí `LumiPrintAgent` / `LumiPrintAgent.exe` **una vez**.
3. El agente se copia solo a una ruta de usuario (sin admin):
   - Windows: `%LOCALAPPDATA%\Lumi\print-agent\`
   - macOS: `~/Library/Application Support/Lumi/print-agent/`
   - Linux: `~/.local/share/lumi/print-agent/`
4. Relanza desde esa copia. Ahí sí podés activar **Arrancar al iniciar sesión**.

Autostart (usuario de caja, no servicio SYSTEM):

- Windows: `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` (`LumiPrintAgent`)
- macOS: `~/Library/LaunchAgents/tech.omayka.lumi-print-agent.plist`
- Linux: `~/.config/autostart/lumi-print-agent.desktop`

Si el puerto `17890` ya responde `/health`, esta copia sale: el agente ya está corriendo.

Desinstalar: desmarcar autostart y borrar la carpeta de usuario.

Modo portable (no copiar): `LUMI_PRINT_PORTABLE=1` o flag `--portable`.

## GUI

- Estado: escuchando `:17890`, impresora elegida, último trabajo / error
- Host / puerto `9100`, descubrir LAN, test print **con corte** (`GS V 0`)
- Toggle autostart (después del self-install)
- Bandeja: Abrir / Probar / Salir

## API local

CORS solo `localhost` / `127.0.0.1` (Chrome del POS).

| Método | Path | Descripción |
|--------|------|-------------|
| GET | `/health` | `{ status: ok }` |
| GET | `/status` | Puerto, impresora, último job |
| GET | `/discover?cidr=` | Ticketeras LAN `:9100` |
| GET | `/printers?cidr=` | CUPS + LAN |
| POST | `/print-direct` | `{ driver_id, connection_detail, content_base64 }` |
| POST | `/ui/open` | Muestra la ventana (si hay GUI) |
| POST | `/process-once` | Un ciclo de cola cloud (si hay API key) |

El POS de Lumi (`localPrintAgent.ts`) ya usa esta API. No cambia la URL.

Bind default: `127.0.0.1:17890`. En sucursal (branch-server) se puede pasar `--host 0.0.0.0`.

## Desarrollo

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[gui,dev]"
python -m lumi_print_gui
# o solo el tubo:
python -m lumi_print_agent --no-poll
```

Python **3.8** es el piso (Win7). En macOS/Linux de desarrollo, 3.10+.

### macOS + pyenv: `libtk8.6.dylib` no found

pyenv compilado contra Tcl/Tk 8.6 se rompe cuando Homebrew pasa a Tcl/Tk 9.

```bash
brew install tcl-tk@8
# o: ./packaging/macos-fix-tkinter.sh
python -m lumi_print_gui
```

La GUI relanza sola el proceso con `DYLD_FALLBACK_LIBRARY_PATH` si encuentra `tcl-tk@8`. Si no:

```bash
export DYLD_FALLBACK_LIBRARY_PATH="$(brew --prefix tcl-tk@8)/lib${DYLD_FALLBACK_LIBRARY_PATH:+:$DYLD_FALLBACK_LIBRARY_PATH}"
python -m lumi_print_gui
```

O recreá el venv con Homebrew Python (incluye Tk):

```bash
brew install python@3.13 python-tk@3.13
/opt/homebrew/bin/python3.13 -m venv .venv --clear
source .venv/bin/activate
pip install -e ".[gui,dev]"
python -m lumi_print_gui
```

El tubo HTTP no necesita Tk: `python -m lumi_print_agent --no-poll`.

Config: `%LOCALAPPDATA%\Lumi\print-agent\config.yaml` (o `LUMI_PRINT_AGENT_CONFIG`). Ver `config.example.yaml`.

Tests:

```bash
python -m pytest -q
```

## Builds (local)

No hay Inno/MSI/.deb en esta entrega. Releases oficiales: ver **Descargas** arriba.

```bash
./packaging/sync-version.sh v0.1.0   # opcional en local
./packaging/build-linux.sh
./packaging/build-macos.sh
./packaging/package-artifact.sh linux x86_64
```

Windows 7+ (artefacto portable): **CPython 3.8**. En CI se usa un runner Windows moderno + Python 3.8 (no hace falta VM Win7).

```powershell
py -3.8 -m pip install -e ".[gui,packaging]"
powershell -File packaging/build-win7.ps1
```

CI (`.github/workflows/ci.yml`): tests. Release (`.github/workflows/release.yml`): binarios + GitHub Release + espejo en vps2.

Stack estático del espejo: `deploy/downloads/` (nginx + Traefik, fuera del compose de Lumi prod).

## Embed en branch-server (headless)

El mismo código, sin tkinter ni bandeja. El branch-server **no se cablea en esta entrega**; el contrato es:

```bash
pip install "lumi-print-agent[headless]"   # extra vacío; el núcleo ya incluye YAML/requests
python -m lumi_print_agent --no-poll --host 0.0.0.0 --port 17890
# o:
lumi-print-agent-headless --no-poll
LUMI_PRINT_HEADLESS=1 lumi-print-agent --host 0.0.0.0
```

- Paquete importable: `lumi_print_agent` (`local_api`, `drivers`, `discover`). Sin tkinter.
- Extra `lumi-print-agent[gui]` = pystray + Pillow (solo el instalador de caja).
- Extra `lumi-print-agent[headless]` = alias documentado (sin deps extra).
- Misma API (`/health`, `/print-direct`, `/printers`). En sucursal se puede bind LAN.
- Flag `--headless` / env `LUMI_PRINT_HEADLESS=1`.
- Versionado semver de este repo: el branch-server pinea una versión; no copiar el árbol a mano.

systemd (box de sucursal), ejemplo:

```ini
[Service]
ExecStart=/opt/lumi/venv/bin/lumi-print-agent-headless --no-poll --host 0.0.0.0
Environment=LUMI_PRINT_HEADLESS=1
```

## Layout

- `lumi_print_agent/` — núcleo (pipe + poll apagado)
- `lumi_print_gui/` — ventana, bandeja, self-install, autostart
- `packaging/` — PyInstaller, sync-version, package-artifact
- `deploy/downloads/` — compose nginx + Traefik para downloads.lumi.com.py
- `tests/`
