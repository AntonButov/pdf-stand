# Deploy pdf-stand

> Проверено: 2026-11-15

| | |
|--|--|
| Host | **80.87.196.33** only |
| Path | `/opt/pdf-stand` |
| Port | **8131** → container `8080` |
| Health | `http://80.87.196.33:8131/health` |

**Not on** `206.223.250.251` (landing only).

Secrets (GitHub repo): `DEPLOY_SSH_PRIVATE_KEY`, `DEPLOY_USER` (`root`).

Push to `main` → workflow `deploy` (pytest then docker compose).
