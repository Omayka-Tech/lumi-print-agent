# Descargas estáticas — Lumi Print Agent

Stack **aparte** del compose de Lumi prod. Solo sirve el árbol
`/opt/lumi/subprojects/downloads/printer-agent` en
`https://downloads.lumi.com.py/`.

## Seguridad

- Bind mount **solo** `printer-agent` → `/usr/share/nginx/html` (no `/opt/lumi`).
- `autoindex off`; el índice lo genera el job de release (`index.html` curado).
- Router Traefik `Host(downloads.lumi.com.py)` con prioridad 200 (por encima del wildcard de prod).

## Arranque (vps2, una vez)

```bash
sudo mkdir -p /opt/lumi/subprojects/downloads/printer-agent/latest
# Owner: usuario del runner (lumi) + lectura para el uid de nginx alpine (101).
sudo chown -R lumi:lumi /opt/lumi/subprojects/downloads
sudo chmod -R u=rwX,go=rX /opt/lumi/subprojects/downloads

# Copiar este directorio al host (o clonar el repo y apuntar aquí):
cp docker-compose.yml nginx.conf /opt/lumi/subprojects/downloads/
cd /opt/lumi/subprojects/downloads
docker compose up -d
```

DNS: registro A/AAAA `downloads.lumi.com.py` → IP de vps2.

Opcional (recomendado): agregar `downloads.lumi.com.py` a la lista de hosts
reservados del nginx prod de Lumi, para que si este stack está caído el
wildcard no sirva el SPA en ese host.

## Publicación

El workflow `release.yml` del repo `lumi-print-agent`, job `publish-downloads`
(self-hosted `[self-hosted, linux, lumi]`), espeja cada tag `v*` a:

```text
/opt/lumi/subprojects/downloads/printer-agent/vX.Y.Z/
/opt/lumi/subprojects/downloads/printer-agent/latest/
/opt/lumi/subprojects/downloads/printer-agent/index.html
```

No hace falta SSH ni secrets de deploy: el runner escribe en disco local.
