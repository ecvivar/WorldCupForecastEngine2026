# Auditoría General — World Cup Forecast Engine 2026

**Fecha:** 2026-06-11  
**Alcance:** Backend (Python/FastAPI/SQLAlchemy), Frontend (Next.js/TypeScript), Motor de predicción, Datos, Infraestructura  
**Tipo:** Técnica + Funcional + Coherencia de métricas

---

## Índice

1. [Resumen Ejecutivo](#1-resumen-ejecutivo)
2. [Capa de Datos: Modelos y Relaciones](#2-capa-de-datos)
3. [Capa de API: Endpoints y Enrutamiento](#3-capa-de-api)
4. [Motor de Predicción: IGF, Match Prediction, Monte Carlo](#4-motor-de-predicción)
5. [Calibración y Refinamiento](#5-calibración-y-refinamiento)
6. [Consistencia Frontend-Backend](#6-consistencia-frontend-backend)
7. [Configuración y Seguridad](#7-configuración-y-seguridad)
8. [Seeding y Calidad de Datos](#8-seeding-y-calidad-de-datos)
9. [Infraestructura y Caching](#9-infraestructura-y-caching)
10. [Conclusiones y Recomendaciones](#10-conclusiones)

---

## 1. Resumen Ejecutivo

El sistema es funcionalmente completo y operativo en Docker. Se identificaron **3 hallazgos críticos**, **8 de alta severidad** y **12 de severidad media** que afectan la coherencia de las predicciones, la reproducibilidad científica y la seguridad en producción.

### Hallazgos Críticos

| # | Hallazgo | Impacto |
|---|----------|---------|
| C1 | **IGF inconsistente**: 3 implementaciones distintas del mismo cálculo producen resultados diferentes | Las predicciones de partidos y las simulaciones Monte Carlo usan métricas de fuerza distintas → incoherencia interna del pipeline |
| C2 | **Sudáfrica sin metadatos**: `TEAM_META` no incluye "Sudáfrica" → `fifa_code=None`, `continent='Unknown'` | Datos huérfanos; error potencial en rankings y exportaciones |
| C3 | **SECRET_KEY por defecto**: `"change-me-in-production"` permite forjar cualquier JWT | Todo el sistema de autenticación es vulnerable en producción |

---

## 2. Capa de Datos

### 2.1 Modelos (11 tablas)

| Tabla | Columnas | PK | FKs | Índices | ¿Unique? |
|-------|----------|----|-----|---------|----------|
| `competitions` | 6 | UUID | – | name | No |
| `teams` | 7 | UUID | – | name, fifa_code | `fifa_code` UNIQUE |
| `groups` | 4 | UUID | competition_id | competition_id | No |
| `group_standings` | 15 | UUID | group_id, team_id | group_id, team_id | No |
| `matches` | 13 | UUID | competition_id, home_team_id, away_team_id | competition_id, home_team_id, away_team_id, match_date | No |
| `players` | 10 | UUID | team_id | team_id | No |
| `elo_ratings` | 5 | UUID | team_id | team_id, rating_date | No |
| `fifa_rankings` | 7 | UUID | team_id | team_id, ranking_date | No |
| `xg_metrics` | 9 | UUID | team_id | team_id, metric_date | No |
| `simulations` | 8 | UUID | competition_id | competition_id | No |
| `simulation_results` | 12 | UUID | simulation_id, team_id | simulation_id, team_id | No |

### 2.2 Hallazgos — Modelos

| # | Severidad | Hallazgo |
|---|-----------|----------|
| M1 | **MEDIO** | Ninguna tabla tiene `unique` compuesto. `(competition_id, name)` en `groups`, `(simulation_id, team_id)` en `simulation_results`, `(team_id, metric_date)` en `xg_metrics` — todos podrían tener duplicados |
| M2 | **BAJO** | `GroupStanding.position` no tiene unique constraint por grupo → dos equipos podrían compartir posición |
| M3 | **BAJO** | `Match.status` es `String(20)` sin enum/constraint → valores inválidos no se rechazan |
| M4 | **BAJO** | `SimulationResult.team_name` en schema es `@property` que retorna `""` → el endpoint lo sobreescribe manualmente como dict key |

---

## 3. Capa de API

### 3.1 Endpoints (49 totales)

- **GET**: 37 | **POST**: 9 | **PATCH**: 1 | **DELETE**: 1
- **Con `@cached`**: 28 | **Con rate limiting**: 6
- **Con `get_db`**: 40 | **Con paginación**: 7

### 3.2 Enrutamiento — Inconsistencias

| # | Severidad | Ruta | Ubicación real | Ubicación esperada |
|---|-----------|------|----------------|---------------------|
| R1 | **BAJO** | `GET /simulations/{id}/probabilities` | `dashboard.py` | `simulations.py` |
| R2 | **BAJO** | `GET /rankings/power-ranking` | `analysis.py` | `rankings.py` |
| R3 | **BAJO** | `GET /predictions/full/{id}` | `analysis.py` | `predictions.py` |
| R4 | **BAJO** | `GET /predictions/betting/{id}` | `analysis.py` | `predictions.py` |
| R5 | **BAJO** | `competitions` no está en `__init__.py` | solo en `main.py` | también en `__init__.py` |

### 3.3 Hallazgos — API

| # | Severidad | Hallazgo |
|---|-----------|----------|
| A1 | **MEDIO** | No hay endpoints PUT (solo PATCH para equipos). No hay operaciones bulk |
| A2 | **BAJO** | `predictions/full/{match_id}` y `matches/{match_id}/prediction` tienen propósitos solapados pero distintos formatos de respuesta |
| A3 | **INFO** | `simulation_probabilities` importa `HTTPException` dentro de la función (patrón no estándar) |
| A4 | **INFO** | 6 endpoints con rate limit (10/min predictions, 5/min simulations y scenarios) |

---

## 4. Motor de Predicción

### 4.1 IGF — Índice de Fuerza Global

**Propósito:** Score compuesto 0–100 por equipo usando 8 factores ponderados.

**Factores y pesos:**

| Factor | Peso | Fuente |
|--------|------|--------|
| Elo | 25% | elo_ratings |
| Forma reciente | 20% | (no especificado) |
| xG a favor | 12% | xg_metrics |
| xG en contra | 8% | xg_metrics |
| Fuerza del oponente | 10% | (no especificado) |
| Experiencia en mundiales | 10% | (no especificado) |
| Calidad de plantilla | 10% | (no especificado) |
| Historial en torneos | 5% | (no especificado) |

### HALLAZGO CRÍTICO C1 — IGF Inconsistente

Existen **3 implementaciones distintas** del IGF que producen resultados diferentes:

| Ruta | Archivo | Fórmula | Rango |
|------|---------|---------|-------|
| **A — IGF completo** | `ranking_service.py` | IGFEngine.compute_team_scores() (8 factores normalizados) | 0–100 |
| **B — Elo-only (simulación)** | `simulation_service.py:112` | `min(1.0, max(0.0, (elo_score - 1300) / 800))` | 0–1 |
| **C — Elo-only (predicción)** | `match_service.py:62`, `predictions.py:67`, `analysis.py:48`, `dashboard.py:39`, `scenarios.py:88` | `min(100.0, max(0.0, (elo_score - 1300) / 8))` | 0–100 |

**Impacto:**
- Las predicciones de partidos (Ruta C) usan una fuerza distinta a las simulaciones Monte Carlo (Ruta B)
- El ranking público (Ruta A) muestra IGF diferente al usado internamente
- El pipeline no es internamente consistente

---

### 4.2 Match Prediction Engine

**4 modelos:**

| Modelo | Fórmula clave | Hallazgos |
|--------|---------------|-----------|
| **Poisson** | `λ_home = exp(IGF_home/50 - IGF_away/50 + 0.08)` | Home advantage = +0.08 en log-λ |
| **Dixon-Coles** | Poisson con corrección τ para scores bajos | Solo ajusta 4 scores (0-0,0-1,1-0,1-1), no continuo |
| **Elo** | `E_home = 1/(1+10^((away_elo - home_elo + 100)/400))` | Home advantage = +100 Elo pts |
| **Full** | Combinación Bayesian de los 3 anteriores + Confidence Index | Prior strength = 2.0 |

### Hallazgos — Match Prediction

| # | Severidad | Hallazgo |
|---|-----------|----------|
| P1 | **MEDIO** | **Home advantage inconsistente**: Poisson usa +0.08 (log-λ ≈ 8% más goles), Elo usa +100 (≈ 25% más goles). No son equivalentes |
| P2 | **MEDIO** | **Dixon-Coles truncado**: Solo ajusta 4 scores (0-0, 0-1, 1-0, 1-1). El modelo original aplica ajuste continuo |
| P3 | **BAJO** | `max_goals=10` → matriz Poisson 11×11. Scores extremos (>10) tienen probabilidad ~0.01% pero se pierden |
| P4 | **BAJO** | **Confidence Index ignora varianza**: Solo usa diferencial de rating, no incertidumbre del modelo |

---

### 4.3 Monte Carlo — Simulación de Torneo

**Pipeline:**
1. Fase de grupos: Poisson(λ) para cada partido, λ = `exp(strength_i - strength_j)`
2. Tiebreakers FIFA: Puntos → GD → GF → GA (bubble sort en Numba)
3. Knockout: Poisson(λ), si empate → extra time (λ×0.33), si aún empate → penalties (50/50)

### Hallazgos — Monte Carlo

| # | Severidad | Hallazgo |
|---|-----------|----------|
| S1 | **ALTO** | **Bracket no oficial**: El emparejamiento es secuencial (winner[0] vs runner_up[0], etc.). FIFA 2026 tiene un bracket fijo con emparejamientos específicos por letra de grupo |
| S2 | **ALTO** | **Simulaciones no reproducibles**: `np.random.seed(seed)` no afecta al RNG interno de Numba. Misma semilla produce resultados diferentes cada ejecución |
| S3 | **ALTO** | **Race condition en paralelo**: `ProcessPoolExecutor` (4 workers) + Numba RNG no fork-safe → streams correlacionados |
| S4 | **MEDIO** | **Extra time = Poisson(0.33λ)**: Aproximación razonable pero no modela cansancio, sustituciones, ni juego conservador |
| S5 | **MEDIO** | **Penalties = 50/50**: Ignora calidad del equipo en penales. Históricamente, equipos con mejor Elo ganan ~55% de tandas |
| S6 | **BAJO** | **Group position nunca se guarda**: `TournamentResult.group_position` siempre es `None` en BD |

### 4.4 Coherencia entre módulos

| Pipeline | Fuerza usada | ¿Consistente con? |
|----------|-------------|-------------------|
| Match predictions (API) | Elo-only (Ruta C, 0–100) | ❌ No con simulaciones |
| Monte Carlo (simulaciones) | Elo-only (Ruta B, 0–1) | ❌ No con predictions |
| IGF rankings (público) | IGF completo (Ruta A, 0–100) | ❌ No con ninguno interno |

**Conclusión:** El sistema tiene 3 escalas de fuerza distintas que no son intercambiables. Las probabilidades de partido y las probabilidades de simulación provienen de modelos que miden la "fuerza" de forma diferente.

---

## 5. Calibración y Refinamiento

### 5.1 Calibración

- **Datos históricos**: 192 partidos (2014, 2018, 2022)
- **Métricas**: Brier Score, Log Loss, Accuracy, ECE, AUC-ROC
- **Análisis de sesgos**: Home, favorite, draw, underdog, confederación

### 5.2 Refinamiento

3 métodos de calibración post-hoc:
1. **Isotonic Regression** — PAV algorithm (sklearn)
2. **Platt Scaling** — Logistic regression con C=1e6
3. **Temperature Scaling** — L-BFGS-B, bounds [0.01, 10.0]

### Hallazgos — Calibración

| # | Severidad | Hallazgo |
|---|-----------|----------|
| K1 | **ALTO** | **`home_advantage=False` en calibración**: Las predicciones se evalúan sin ventaja local contra partidos históricos que SÍ tenían localía. Esto subestima sistemáticamente las victorias locales |
| K2 | **MEDIO** | **Isotonic Regression almacena datos crudos**: Guarda todos los puntos x/y del entrenamiento en vez de un modelo serializable |
| K3 | **MEDIO** | **Platt Scaling con C=1e6**: Sin regularización efectiva → puede sobreajustar |
| K4 | **BAJO** | `favorite_bias` en realidad mide accuracy (no bias). Nombre engañoso |
| K5 | **BAJO** | Isotonic multi-class: 3 modelos independientes + renormalización → puede producir artefactos |

---

## 6. Consistencia Frontend-Backend

### 6.1 Mapeo General

- **35 métodos API** en el frontend
- **18 páginas** que consumen datos
- **~25 formas de datos** distintas

### 6.2 Hallazgos — Tipos

| # | Severidad | Hallazgo |
|---|-----------|----------|
| F1 | **MEDIO** | **`api.matches.predict()`** tipado como `FullMatchPrediction` pero el backend retorna `MatchPrediction` (objeto más simple). No se usa en producción, pero es un error latente |
| F2 | **BAJO** | `FullMatchPrediction` declara `stage?`, `group_name?`, `match_date?` que el backend no retorna (nunca se consumen) |
| F3 | **BAJO** | `GroupStanding` no incluye `xg_for`/`xg_against` que el backend sí retorna (ignorados, sin impacto) |
| F4 | **BAJO** | `CalibrationReport.bias` tipado como `Record<string, number>` pero backend retorna objeto estructurado (serialización compatible) |
| F5 | **BAJO** | `CalibrationMetric` no incluye `n_matches` del backend |

### 6.3 Conclusión Frontend-Backend

**33 de 35 métodos** tienen tipos correctos o con diferencias benignas. El contrato frontend-backend está **altamente alineado**. Solo 1 error de tipo latente.

---

## 7. Configuración y Seguridad

### 7.1 Variables de Entorno (31 totales)

| Categoría | Variables |
|-----------|-----------|
| Base de datos | `DATABASE_URL`, `DATABASE_ECHO`, `DATABASE_POOL_SIZE`, `DATABASE_MAX_OVERFLOW` |
| Redis/Cache | `REDIS_URL`, `CACHE_TTL` |
| JWT/Auth | `SECRET_KEY`, `JWT_ALGORITHM`, `JWT_EXPIRE_MINUTES`, `JWT_REFRESH_EXPIRE_DAYS` |
| CORS | `CORS_ORIGINS` |
| Logging/Monitoring | `LOG_LEVEL`, `SENTRY_DSN`, `SENTRY_ENVIRONMENT` |
| Collectors | 6 URLs + `FOOTBALL_DATA_API_KEY` |
| Engine | `ENGINE_DEFAULT_SIMULATIONS`, `ENGINE_POISSON_MAX_GOALS`, `ENGINE_ELO_K_FACTOR`, `ENGINE_ELO_INITIAL_RATING` |
| IGF | 8 pesos configurables (`IGF_*_WEIGHT`) |

### 7.2 Hallazgos — Seguridad

| # | Severidad | Hallazgo |
|---|-----------|----------|
| SEG1 | **CRÍTICO** | `SECRET_KEY` por defecto `"change-me-in-production"` — solo emite warning, no impide el arranque |
| SEG2 | **ALTO** | Credenciales PostgreSQL hardcodeadas en URL por defecto (`postgres:postgres`) |
| SEG3 | **MEDIO** | JWT con HS256 (simétrico). Si la clave se filtra, cualquier token es forjable. RS256 sería más seguro |
| SEG4 | **MEDIO** | No hay validación de longitud mínima para `SECRET_KEY` |
| SEG5 | **MEDIO** | CORS acepta `localhost:3000,3001` — debe restringirse en producción |
| SEG6 | **BAJO** | **No hay CORS middleware implementado**: La config `cors_origins` existe pero no hay `CORSMiddleware` en la app. Las peticiones cross-origin serían bloqueadas por el navegador |
| SEG7 | **BAJO** | HSTS `max-age=31536000; includeSubDomains` se envía incluso si no hay HTTPS |

---

## 8. Seeding y Calidad de Datos

### 8.1 Datos Sembrados

| Entidad | Cantidad | Detalle |
|---------|----------|---------|
| Competition | 1 | FIFA World Cup 2026 |
| Teams | 48 | 12 grupos × 4 equipos |
| EloRating | 48 | 1 por equipo, `date.today()` |
| FifaRanking | 48 | 1 por equipo, `date.today()` |
| XGMetrics | 48 | 1 por equipo, `date.today()` |
| Groups | 12 | A–L |
| GroupStandings | 48 | 1 por equipo, stats en 0 |
| Matches | 72 | 6 por grupo (round-robin) |

### 8.2 Fórmulas de Seed

**Elo:** `1500 + (48 - i) × 20` → México 2460, Panamá 1520  
**FIFA:** `1800.0 - i × 15` → México 1800, Panamá 1095  
**xG for:** `2.5 - i × 0.04` → México 2.50, Panamá 0.62  
**xG against:** `0.8 + i × 0.03` → México 0.80, Panamá 2.21  

> **Nota:** Todos los valores dependen del orden de iteración del diccionario (orden de inserción). No reflejan la fuerza real de los equipos.

### 8.3 Hallazgos — Seed

| # | Severidad | Hallazgo |
|---|-----------|----------|
| D1 | **CRÍTICO** | **Sudáfrica no está en `TEAM_META`**: `TEAM_META.get("Sudáfrica", (None, 'Unknown', None))` → `fifa_code=None`, `continent='Unknown'`. Cada vez que se consulta `team.fifa_code` o `team.continent`, será nulo |
| D2 | **ALTO** | **Nigeria en `TEAM_META` pero no en ningún grupo**: Existe como equipo pero sin group standing ni partidos → dato huérfano |
| D3 | **ALTO** | **Fuerzas basadas en orden de inserción**: México (1° en iteración) tiene Elo 2460, Panamá (48°) tiene 1520. Esto es arbitrario, no refleja la realidad |
| D4 | **MEDIO** | **No hay partidos de knockout**: Solo fase de grupos. Para un torneo `group_plus_knockout`, faltan los cruces |
| D5 | **MEDIO** | **Posiciones de group standing = orden de lista**: No reflejan posiciones reales; todos los equipos empiezan en posición 1–4 según el orden en que se listaron |
| D6 | **BAJO** | **48 flushes individuales** en vez de batch |
| D7 | **BAJO** | **`date.today()` para ratings**: Si el seed corre en otra fecha, las fechas cambian |

---

## 9. Infraestructura y Caching

### 9.1 Cache Decorator (`@cached`)

- **Patrón**: Cache-Aside (check → compute → store)
- **TTLs por prefix**: 120s (dashboard), 300s (rankings/groups/predictions), 600s (teams/matches), 1800s (calibration/benchmark), 3600s (simulations)
- **Clave**: `{prefix}:{arg1=val1|arg2=val2}` (excluye `db`, `session`, `request`)

### 9.2 Hallazgos — Cache

| # | Severidad | Hallazgo |
|---|-----------|----------|
| H1 | **ALTO** | **Síncrono** — `get_sync`/`set_sync` bloquean el event loop si se usa en endpoints async |
| H2 | **MEDIO** | **Sin cache locking**: Dos requests concurrentes por misma clave pueden ejecutar el cómputo dos veces (thundering herd) |
| H3 | **MEDIO** | **Sin invalidación automática**: El decorador no provee forma de invalidar caché tras escrituras |
| H4 | **BAJO** | **Sin métricas de cache miss** en el decorador (solo dentro de `RedisCacheService`) |

### 9.3 Healthchecks

- **DB**: `pg_isready` (funciona)
- **Redis**: `redis-cli ping` (funciona)
- **Backend**: `python -c "urllib.request.urlopen('http://localhost:8000/health')"` (corregido, funciona)
- **Frontend**: Sin healthcheck

### 9.4 Middleware

| Middleware | Estado |
|------------|--------|
| SecurityHeadersMiddleware | ✅ Activo (CSP, HSTS, X-Frame, etc.) |
| MetricsMiddleware | ✅ Activo (request count, duration) |
| CORS Middleware | ❌ **No implementado** |
| Rate Limiting Middleware | ❌ No implementado (rate limit solo por decorador en 6 endpoints) |
| Auth/JWT Middleware | ❌ No implementado |
| Request Logging | ❌ No implementado (solo logs de Gunicorn) |

---

## 10. Conclusiones

### 10.1 Resumen por Severidad

| Severidad | Cantidad | IDs |
|-----------|----------|-----|
| **CRÍTICO** | 3 | C1 (IGF inconsistente), C2 (Sudáfrica sin meta), C3 (SECRET_KEY default) |
| **ALTO** | 8 | S1 (bracket no oficial), S2 (sims no reproducibles), S3 (race condition Numba), K1 (home_advantage=False), D2 (Nigeria huérfano), D3 (fuerzas arbitrarias), H1 (cache síncrono), SEG2 (creds hardcodeadas) |
| **MEDIO** | 12 | M1 (sin unique compuestos), P1 (home advantage inconsistente), P2 (Dixon-Coles truncado), S4 (extra time simplificado), S5 (penales 50/50), K2 (isotonic raw data), K3 (Platt sin regularización), F1 (tipo erróneo en api.matches.predict), SEG3 (HS256), SEG4 (no min-length secret), H2 (no cache locking), D4 (sin knockouts) |
| **BAJO** | ~15 | Varios (tipos benignos, estética, documentación) |

### 10.2 Recomendaciones Prioritarias

1. **Unificar IGF**: Usar el IGF completo (8 factores) de forma consistente en `simulation_service.py`, `match_service.py`, `predictions.py`, `analysis.py`, `dashboard.py` y `scenarios.py`. Eliminar las Rutas B y C.

2. **Corregir seed data**: Agregar "Sudáfrica" a `TEAM_META` con sus datos reales. Quitar "Nigeria" o asignarla a un grupo. Idealmente, reemplazar las fuerzas basadas en orden de inserción por valores reales de ranking FIFA/Elo.

3. **Hardened SECRET_KEY**: Que la app **no arranque** si `SECRET_KEY` es el default o tiene menos de 32 caracteres.

4. **Implementar bracket FIFA 2026**: Reemplazar el emparejamiento secuencial en `monte_carlo.py` por la matriz oficial de emparejamientos fijos.

5. **Arreglar reproducibilidad de simulaciones**: Usar `np.random.RandomState` con seed controlado dentro de las funciones Numba, o migrar a `numpy.random.Generator`.

6. **Corregir home_advantage en calibración**: Re-ejecutar calibración con `home_advantage=True` para obtener métricas realistas.

7. **Unificar home advantage**: Decidir si la ventaja local es +0.08 (Poisson) o +100 Elo (Elo) y usar el mismo valor en ambos modelos.

8. **Implementar CORS middleware**: Usar `fastapi.middleware.cors.CORSMiddleware` con `allow_origins` desde `settings.cors_origins`.

### 10.3 Coherencia General del Sistema

**Fortalezas:**
- Arquitectura modular y bien separada (modelos → servicios → API → frontend)
- Tipado consistente entre frontend y backend (33/35 métodos correctos)
- Cache-Aside implementado con TTLs diferenciados por tipo de dato
- Calibración contra 192 partidos históricos con 4 métricas distintas
- 4 modelos de predicción (Poisson, Dixon-Coles, Elo, Full)
- Monte Carlo con Numba JIT para alto rendimiento (~100K simulaciones)

**Debilidades principales:**
- **Incoherencia interna del pipeline**: Las predicciones de partido y las simulaciones miden la "fuerza" del equipo con escalas distintas. Es el problema más grave porque significa que las probabilidades mostradas al usuario provienen de modelos que no están sincronizados.
- **Datos semilla no realistas**: Las fuerzas iniciales se basan en orden arbitrario, no en datos reales. Esto afecta todas las predicciones hasta que se recopilen datos reales.
- **Simulaciones no reproducibles**: Sin seeds funcionales en Numba, no se pueden verificar ni depurar resultados de simulación.
- **Seguridad**: La aplicación arranca con secretos por defecto y sin CORS middleware.

### 10.4 Métricas del Sistema (Post-Fix)

| Métrica | Valor |
|---------|-------|
| Endpoints funcionando | 49/49 (100%) |
| Equipos con datos completos | 47/48 (Sudáfrica parcial) |
| Grupos con standings | 12/12 |
| Partidos sembrados | 72 (solo grupo) |
| Modelos de predicción | 4 |
| Simulaciones paralelas | 4 workers |
| Cobertura de caché | 28/49 endpoints |
| Rate limiting | 6/49 endpoints |
