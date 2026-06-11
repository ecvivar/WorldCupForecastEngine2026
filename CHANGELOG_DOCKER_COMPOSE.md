# Cambios Realizados para `docker compose up`

## `backend/Dockerfile`

**Problema:** `pip install --user` instalaba las dependencias en `/root/.local`, pero el usuario `app` (uid 1001) no tiene acceso de lectura a `/root/`. La instrucción `COPY --from=builder /root/.local /root/.local` copiaba a un directorio inaccesible.

**Solución:**
- Se eliminó el flag `--user` del `pip install`.
- El `COPY --from=builder` ahora copia `/usr/local` (donde pip instala por defecto sin `--user`), que es world-readable.

---

## `backend/docker-entrypoint.sh`

### 1. Conversión CRLF → LF

**Problema:** El archivo tenía terminaciones CRLF (Windows). En el contenedor Linux, el shebang `#!/bin/bash` falla con `\r\n` porque `bash` no reconoce `#!/bin/bash\r` como un shebang válido.

**Solución:** Convertir el archivo a LF (Unix) usando `sed -i 's/\r$//'`.

### 2. Imports de modelos para el seed

**Problema:** El script de seed (`seed_initial_data.py`) usa modelos SQLAlchemy como `Competition`, `Team`, `Player`, etc. Si estos no están importados antes de ejecutar el seed, SQLAlchemy lanza `InvalidRequestError: When initializing mapper ... failed to locate a name`.

**Solución:** Agregar `from app.models import ...` explícito para `Player` y `simulation` (Simulation, SimulationResult) antes de llamar al seed, asegurando que todos los mappers estén registrados.

---

## `backend/requirements.txt`

### 1. `psycopg[binary]==3.2.1`

**Problema:** PostgreSQL se conecta via `psycopg://` (esquema de psycopg v3). La imagen `python:3.11-slim` no incluye `libpq` (necesario para compilar psycopg desde fuente). Sin `psycopg[binary]`, el driver no se instala y la DB connection string falla.

**Solución:** Agregar `psycopg[binary]==3.2.1` para usar las ruedas binarias precompiladas que no requieren `libpq`.

### 2. `scikit-learn==1.5.1`

**Problema:** El módulo `app.engine.calibration_refinement` importa `sklearn.isotonic.IsotonicRegression` y `sklearn.linear_model.LogisticRegression`. Como `app.api.__init__` importa `calibration_refinement`, Gunicorn intenta cargarlo al arrancar y falla con `ModuleNotFoundError: No module named 'sklearn'`.

**Solución:** Agregar `scikit-learn==1.5.1` a las dependencias.

---

## `frontend/Dockerfile`

**Problema:** `npm ci --only=production` no es un flag válido de npm. El flag correcto es `--omit=dev` (introducido en npm v8+). El comando fallaba al construir la imagen.

**Solución:** Reemplazar `--only=production` por `--omit=dev`.

---

## `frontend/package.json`

**Problema:** `@next/swc-win32-x64-msvc` es una dependencia nativa de Windows. En la build Docker (Linux x86_64), npm intenta instalarla pero falla porque es una plataforma incorrecta. Estaba en `dependencies`, por lo que npm intenta resolverla siempre.

**Solución:** Mover `@next/swc-win32-x64-msvc` de `dependencies` a `optionalDependencies`. En Linux se omite silenciosamente; en Windows sigue estando disponible si es necesario.

---

## `frontend/public/` (directorio)

**Problema:** El Dockerfile del frontend tiene `COPY --from=builder /app/public ./public`. Si el directorio `public/` no existe en el contexto de build, Docker falla.

**Solución:** Crear el directorio `frontend/public/` (vacío) para que el COPY no falle.

---

## Archivos nuevos creados

| Archivo | Propósito |
|---------|-----------|
| `docs/GUIA_EJECUCION_LOCAL.md` | Guía de ejecución local en español (Docker Compose y manual) |
| `FRONTEND_PRODUCTION_REPORT.md` | Auditoría de producción del frontend (DEPLOY-006) |
| `RUNBOOK.md` | Runbook de operación y despliegue (DEPLOY-007) |
| `COST_ANALYSIS_REPORT.md` | Análisis de costos mensuales (DEPLOY-008) |
| `PRODUCTION_CERTIFICATION_REPORT.md` | Certificación de producción (DEPLOY-009) |
| `PHASE10_1_PRODUCTION_CLEANUP_REPORT.md` | Reporte de limpieza Phase 10.1 |
| `changes.diff` | Diff de todos los cambios en archivos existentes |

---

## Estado final

- `docker compose up` funciona correctamente con los 4 servicios (db, redis, backend, frontend)
- Backend responde en `http://localhost:8000/health` → `{"status":"ok"}`
- Frontend responde en `http://localhost:3000` → HTTP 200
- Gunicorn arranca con 8 workers (autodetectados por CPU)
- Seed data salta si ya existe (idempotente)
- Numba warm-up se ejecuta antes del fork de workers
