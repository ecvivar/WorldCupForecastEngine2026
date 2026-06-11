# Guía de Ejecución Local — WorldCup Forecast Engine 2026

## Requisitos

| Herramienta | Versión Mínima |
|-------------|----------------|
| Python      | 3.13+ |
| Node.js     | 18+ |
| Docker      | 24+ |
| Docker Compose | 2.20+ |

---

## Opción 1: Docker Compose (recomendado)

Levanta todo el stack (PostgreSQL + Redis + Backend + Frontend) con un solo comando:

```bash
# Desde la raíz del proyecto
docker compose up --build
```

| Servicio  | URL |
|-----------|-----|
| Frontend  | http://localhost:3000 |
| Backend   | http://localhost:8000 |
| Swagger   | http://localhost:8000/docs |
| ReDoc     | http://localhost:8000/redoc |
| PostgreSQL| `localhost:5433` (user: `postgres`, pass: `postgres`, db: `worldcup_forecast`) |
| Redis     | `localhost:6379` |

Los datos de prueba se siembran automáticamente al iniciar.

Para detener: `docker compose down`

---

## Opción 2: Manual (desarrollo)

### 2.1 Backend

```bash
cd backend

# Crear y activar entorno virtual
python -m venv .venv
.\.venv\Scripts\activate   # Windows
source .venv/bin/activate   # Linux/Mac

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno (crear backend/.env)
# Mínimo necesario para desarrollo local:
cat > .env << EOF
DATABASE_URL=sqlite:///./dev.db
REDIS_URL=
SECRET_KEY=dev-secret-key-32-chars-minimum!!
CORS_ORIGINS=http://localhost:3000
LOG_LEVEL=INFO
EOF

# Iniciar servidor
uvicorn app.main:app --reload --port 8000
```

La app crea las tablas automáticamente al iniciar (sin migraciones).

**Con PostgreSQL local (Docker):**

```bash
# Levantar solo la base de datos
docker compose up -d db

# En .env usar:
# DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5433/worldcup_forecast

# Sembrar datos
python scripts/seed_data.py
```

### 2.2 Frontend

```bash
cd frontend
npm install
npm run dev
```

Abrir http://localhost:3000

---

## Variables de Entorno Clave

| Variable | Default | Descripción |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+psycopg://postgres:postgres@localhost:5432/worldcup_forecast` | Conexión a base de datos. Usar `sqlite:///./dev.db` para desarrollo sin PostgreSQL |
| `REDIS_URL` | `redis://localhost:6379/0` | Conexión a Redis. Dejar vacío para deshabilitar caché |
| `SECRET_KEY` | `change-me-in-production` | Clave JWT (mínimo 32 caracteres) |
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost:3001` | Orígenes permitidos |
| `LOG_LEVEL` | `INFO` | Nivel de logging |
| `ENGINE_DEFAULT_SIMULATIONS` | `100000` | Simulaciones por defecto en Monte Carlo |

---

## Tests

```bash
cd backend
pytest -v --tb=short -k "not calibration"
```

> Los tests de calibración requieren Python <3.14 por un cambio en `numpy.trapz`. Ignorarlos con `-k "not calibration"`.

---

## Seed Data

El entrypoint de Docker siembra 48 equipos en 12 grupos con 72 partidos automáticamente. En desarrollo manual:

```bash
cd backend
python scripts/seed_data.py
```
