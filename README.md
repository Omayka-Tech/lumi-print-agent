# Lumi Print Agent

Agente local de impresión para [Lumi ERP](https://github.com/Omayka-Tech/lumi-erp). Una ventana, no un POS: habla con la ticketera (Epson TM-T88 y compatibles ESC/POS en `:9100`).

Requiere **Windows 7+** / macOS / Linux. El POS desktop Tauri queda para cajas Win10+.

## Default (esta versión)

Chrome (sesión JWT) pide el ticket a Lumi, y el browser lo manda al agente:

`Chrome → Cloud → Chrome → POST http://127.0.0.1:17890/print-direct → impresora`

La GUI **no pide** URL de Lumi ni API key. El agente es un tubo local.

## Avanzado (después, mismo binario)

`Chrome → Cloud (encola PrintJob) → Agente poll → impresora`

El poll vive en el núcleo (`lumi_print_agent.agent`) y está **apagado**. No hay panel Avanzado en esta entrega.

## Instalación (sin MSI)

1. Bajá el folder `LumiPrintAgent` (PyInstaller onedir) o corré desde fuente.
2. Abrí `LumiPrintAgent.exe` **una vez**.
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

Config: `%LOCALAPPDATA%\Lumi\print-agent\config.yaml` (o `LUMI_PRINT_AGENT_CONFIG`). Ver `config.example.yaml`.

Tests:

```bash
python -m pytest -q
```

## Builds

No hay Inno/MSI/.deb en esta entrega.

```bash
# Linux
./packaging/build-linux.sh

# macOS
./packaging/build-macos.sh
```

Windows 7 (32/64): **CPython 3.8** en una VM Win7 o runner self-hosted. GitHub Actions no ofrece Win7.

```powershell
py -3.8 -m pip install -e ".[gui,packaging]"
powershell -File packaging/build-win7.ps1
```

CI (`.github/workflows/ci.yml`): tests en Ubuntu + macOS (3.8/3.12) y Windows 2019 (exe moderno / tests). El artefacto Win7 se genera en la VM.

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
- `packaging/` — PyInstaller
- `tests/`
