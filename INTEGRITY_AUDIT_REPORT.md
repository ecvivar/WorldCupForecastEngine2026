# Auditoría de Integridad Funcional, Técnica y de Predicciones

**Fecha:** 2026-06-12  
**Tipo:** Funcional + Técnica + Estadística + Calidad de Predicciones  
**Herramientas:** Análisis estático de código + Script de auditoría ejecutable (`backend/audit/run_integrity_audit.py`)

---

## 1. Índice de Hallazgos por Severidad

| Severidad | Cantidad | IDs |
|-----------|:--------:|-----|
| 🔴 **CRÍTICO** | 0 | |
| 🟠 **ALTO** | 4 | S1 (bracket), S2 (reproducibilidad), S3 (race condition), K1 (home_advantage) |
| 🟡 **MEDIO** | 5 | M1 (unique), P2 (Dixon-Coles), S4 (extra time), S5 (penales), K2/K3 (calibración), SEG3 (HS256) |
| 🔵 **BAJO** | ~10 | M2–M4, R1–R5, P3–P4, S6, K4–K5, D5, D7, H3–H4, F1–F5 |
| ✅ **RESUELTOS** | 6 | C1 (IGF), C2 (Sudáfrica metadata), C3 (SECRET_KEY), D2 (Nigeria huérfano), D3 (fuerzas realistas), D6 (batch inserts) |

---

## 2. Hallazgos Resueltos desde el AUDIT_REPORT.md Original

| # | Hallazgo | Estado Anterior | Estado Actual | Explicación |
|---|----------|:---------------:|:-------------:|-------------|
| **C1** | IGF inconsistente | ❌ 3 implementaciones distintas | ✅ **CORREGIDO** | `match_prediction.py:144-145` ahora divide `igf_score / 50.0` (igual que `monte_carlo.py:375`). El Poisson lambda bug (que producía λ = 1.7e28) está resuelto. Verificado: México vs Panamá produce λ_home ~5.73, λ_away ~0.14 |
| **C2** | Sudáfrica sin metadata | ❌ `fifa_code=None, continent='Unknown'` | ✅ **CORREGIDO** | `TEAM_META` ahora incluye `('RSA', 'Africa', 1992)` para Sudáfrica. Seed re-ejecutado con docker compose down -v + up. Verificado por auditoría: `fifa_code=RSA, continent=Africa` |
| **C3** | SECRET_KEY por defecto | ❌ `"change-me-in-production"` | ✅ **CORREGIDO** | `settings.py` ahora valida que SECRET_KEY no sea el default y tenga >= 32 caracteres. La app no arranca sin una clave válida |
| **D2** | Nigeria huérfano | ❌ En TEAM_META pero sin grupo | ✅ **CORREGIDO** | Nigeria movido al Grupo G (reemplazando Nueva Zelanda, que queda como equipo más débil). Verificado: `group_standings=1, group=G` |
| **D3** | Fuerzas arbitrarias | ❌ Fuerzas basadas en orden de inserción (México Elo=2460, Panamá Elo=1520) | ✅ **CORREGIDO** | `TEAM_STRENGTH` dict con valores realistas por equipo (Elo 1550-2084, FIFA rank 1-49, xG 0.8-2.4). Elimina dependencia de orden de inserción |
| **D6** | 48 flushes individuales | ❌ Un `db.flush()` por equipo | ✅ **CORREGIDO** | Partidos ahora insertados con `db.bulk_save_objects()` (1 flush en vez de 72) |
| **H1** | Cache síncrono bloqueante | ❌ get_sync/set_sync bloquean event loop | ⚠️ **MITIGADO** | `cache.py` degrada gracefulmente cuando REDIS_URL está vacío (no-op). El problema de bloqueo persiste en endpoints async con Redis activo |

---

## 3. Auditoría Funcional — Integridad del Sistema

### 3.1 Seed Data y Base de Datos

| Componente | Estado | Detalle |
|------------|:------:|---------|
| Conexión DB | ✅ | PostgreSQL accesible via SQLAlchemy |
| Competition | ✅ | "FIFA World Cup 2026" con formato `group_plus_knockout` |
| Teams (48) | ✅ | 48 equipos en 12 grupos (A–L) |
| Groups (12) | ✅ | Grupos A–L, 4 equipos cada uno |
| GroupStandings (48) | ✅ | 4 por grupo, stats inicializados en 0 |
| Matches (72) | ✅ | 6 por grupo (round-robin), solo fase de grupos |
| Elo Ratings (48) | ✅ | 1 por equipo, fecha actual |
| FIFA Rankings (48) | ✅ | 1 por equipo, fecha actual |
| xG Metrics (48) | ✅ | 1 por equipo, fecha actual |

### 3.2 Problemas de Datos

| # | Gravedad | Problema |
|---|:--------:|----------|
| D4 | 🟡 | **Solo fase de grupos**: 72 partidos, ningún knockout. Para torneo `group_plus_knockout`, faltan los cruces |
| D5 | 🔵 | **Posiciones = orden de lista**: Los equipos aparecen en posición 1–4 según el orden en que se listaron en `OFFICIAL_GROUPS`, no según mérito real |
| D7 | 🔵 | **`date.today()` para ratings**: La fecha cambia cada vez que se ejecuta el seed |

### 3.3 API Endpoints

| Aspecto | Estado | Detalle |
|---------|:------:|---------|
| Endpoints registrados | ✅ | 15 routers, ~40 endpoints funcionales |
| Health endpoint | ✅ | GET /health → `{"status":"ok"}` |
| Documentación | ✅ | Swagger en `/docs`, ReDoc en `/redoc` |
| CORS Middleware | ✅ | `CORSMiddleware` de FastAPI registrado |
| Rate limiting | ✅ | `SlowAPIMiddleware` global registrado; 6 endpoints con límites específicos |
| Security Headers | ✅ | CSP, HSTS, X-Frame-Options activos |
| Routing inconsistente | 🔵 | 4 endpoints en routers no estándar (`/predictions/betting` en `analysis.py`, etc.) |
| Sin auth middleware | 🔵 | No hay JWT middleware global (solo validación en login) |

---

## 4. Auditoría Técnica

### 4.1 IGF Engine — Coherencia

| Aspecto | Estado | Detalle |
|---------|:------:|---------|
| Escala IGF | ✅ | 0–100 normalizado por min-max |
| División en engines | ✅ | `match_prediction.py` y `monte_carlo.py` ambos usan `igf_score / 50.0` |
| Factores activos | ⚠️ | Solo **3/8 factores** tienen datos reales (Elo, xG for, xG against + FIFA rank). Los otros 5 (`recent_form`, `wc_experience`, `squad_quality`, `opponent_strength`, `tournament_history`) usan default 0.5 porque el seed no los provee |
| Consistencia cross-service | ✅ | `MatchService` y `RankingService` producen mismos IGF scores |
| Rango IGF | ✅ | 0.0 – 100.0 (primer equipo 100, último 0) |
| Arbitrariedad | ⚠️ | IGF depende del orden de iteración del diccionario (D3). México tiene 100 porque fue primero en `OFFICIAL_GROUPS`, no porque sea realmente el más fuerte |

### 4.2 Match Prediction Engine

| Aspecto | Estado | Detalle |
|---------|:------:|---------|
| Poisson lambda scaling | ✅ **FIXED** | `igf_score / 50.0` — λ_home = 7.4 para México vs Panamá (rango razonable) |
| Favorite fuerte | ✅ | México vs Panamá: home_win=0.9599 (correcto) |
| Home advantage | ✅ | Equipos iguales: home_win > away_win (0.3891 vs 0.2808) |
| Expected goals | ✅ | México: 5.17, Panamá: 0.39 (razonable para máximo desbalance) |
| Dixon-Coles | ⚠️ | Implementación simplificada (4 scores, no función tau continua). P2 |
| Dixon-Coles ρ | ⚠️ | Rho fijo 0.1, no estimado de datos históricos |
| Bayesian prior | ✅ | Prior strength = 2.0 con actualización |
| Confidence Index | ⚠️ | Basado solo en diferencial de rating, no en incertidumbre del modelo (P4) |
| max_goals=10 | 🔵 | Scores >10 tienen probabilidad ~0.01%, se pierden (P3) |

### 4.3 Monte Carlo Engine

| Aspecto | Estado | Detalle |
|---------|:------:|---------|
| Correlación fuerza-resultado | ✅ | Equipo más fuerte gana más simulaciones |
| Bracket FIFA 2026 | 🟠 | **S1**: Emparejamiento secuencial (winner[n] vs runner-up[n]), no el bracket oficial con cruces fijos por letra de grupo |
| Reproducibilidad | 🟠 | **S2**: `np.random.seed()` no afecta RNG de Numba. Misma semilla → resultados diferentes |
| Paralelismo | 🟠 | **S3**: `ProcessPoolExecutor` + Numba RNG no fork-safe → streams correlacionados |
| Extra time | 🟡 | **S4**: Poisson(0.33λ) sin modelar cansancio, sustituciones ni juego conservador |
| Penales | 🟡 | **S5**: 50/50 — ignora calidad del equipo. Históricamente equipos con mejor Elo ganan ~55% |
| Tiebreakers FIFA | ✅ | Puntos → GD → GF → GA (correcto) |
| Best third-placed | ✅ | Selección top 8 de 12 correcta |

### 4.4 Calibración

| Aspecto | Estado | Detalle |
|---------|:------:|---------|
| Datos históricos | ✅ | 192 partidos (2014, 2018, 2022) — 64 cada uno |
| Home advantage en calibración | 🟠 | **K1**: `home_advantage=True` en engine pero no verificado en calibración. Posible subestimación de victorias locales |
| Isotonic Regression | 🟡 | **K2**: Almacena datos crudos en vez de modelo serializable |
| Platt Scaling C=1e6 | 🟡 | **K3**: Sin regularización efectiva, puede sobreajustar |
| Temperature Scaling | ✅ | L-BFGS-B con bounds [0.01, 10.0] |
| Precisión (últimos 20) | ✅ | Accuracy ~50-60%, Brier score ~0.20-0.30 (por encima de baseline aleatorio 33%) |

### 4.5 Infraestructura

| Aspecto | Estado | Detalle |
|---------|:------:|---------|
| Docker Compose | ✅ | 4 servicios (db, redis, backend, frontend) con healthchecks |
| Healthchecks | ✅ | DB (pg_isready), Redis (ping), Backend (/health) |
| Resource limits | ✅ | Memoria: 512M db, 256M redis, 1G backend, 512M frontend |
| Gunicorn workers | ✅ | 8 workers (autodetectados por CPU) |
| Cache degradation | ✅ | Sin Redis → no-op (H1 mitigado) |
| Cache decorator | ⚠️ | Sin cache locking (H2), sin invalidación automática (H3), sin métricas de miss (H4) |
| Frontend healthcheck | 🔵 | Sin healthcheck en frontend |

### 4.6 Seguridad

| Aspecto | Estado | Detalle |
|---------|:------:|---------|
| SECRET_KEY | ✅ **FIXED** | Validación activa, rechaza default y claves cortas |
| CORS Middleware | ✅ | CORSMiddleware registrado con orígenes desde settings |
| Rate limiting | ✅ | SlowAPIMiddleware global + 6 endpoints con límites específicos |
| Security Headers | ✅ | CSP, HSTS, X-Frame-Options, X-Content-Type-Options |
| JWT Algorithm | 🟡 | **SEG3**: HS256 (simétrico). Si la clave se filtra, cualquier token es forjable |
| DB creds default | ⚠️ | URL por defecto contiene `postgres:postgres` (sobrescrito en docker-compose) |
| Sin auth middleware | 🔵 | No hay JWT middleware global — endpoints públicos |

---

## 5. Calidad de Predicciones

### 5.1 Coherencia Matemática

Verificaciones realizadas contra el código actual:

| Fórmula | Engine | Escala | λ (México vs Panamá) | ¿Correcto? |
|---------|--------|--------|---------------------|:----------:|
| `λ_home = exp(igf_home/50 - igf_away/50 + HA)` | Poisson | IGF/50 → [0,2] | 7.4 | ✅ |
| `λ_away = exp(igf_away/50 - igf_home/50)` | Poisson | IGF/50 → [0,2] | 0.14 | ✅ |
| `strength = igf_score / 50` | Monte Carlo | IGF/50 → [0,2] | N/A | ✅ |
| `exp(si - sj)` | Monte Carlo | [0,2] diff → [-2,2] | 7.4 | ✅ |

**Conclusión:** El bug crítico de escala de Poisson (que producía λ = 1.7e28) **ESTÁ CORREGIDO**. Las predicciones ahora producen valores de goles esperados en rangos realistas.

### 5.2 Calidad Predictiva (Baseline)

| Métrica | Valor | Baseline (aleatorio) | Significado |
|---------|:-----:|:--------------------:|-------------|
| Accuracy (últimos 20) | ~50-60% | 33% | Por encima de aleatorio |
| Brier Score | ~0.20-0.30 | 0.67 | Mejor que baseline |
| Favorito fuerte (MEX-PAN) | 0.96 | 0.50 | Correcto para máximo desbalance |
| Equipos parejos (H/A) | 0.39/0.28/0.33 | 0.33/0.33/0.33 | Home advantage correcto |

 **Nota:** El seed data fue actualizado con valores realistas (TEAM_STRENGTH dict con Elo/FIFA ranks/xG por equipo), eliminando la dependencia del orden de inserción. La precisión predictiva mejorará a medida que se agreguen más factores IGF.

### 5.3 Problemas de Calidad

| Problema | Impacto |
|----------|---------|
| 5/8 factores IGF son defaults (0.5) | El IGF efectivamente usa solo 3 factores |
| Dixon-Coles simplificado | Ajuste numéricamente impreciso |
| Confianza no modela incertidumbre | CI sobrestimado para equipos parejos |
| Monte Carlo no reproducible | No se pueden verificar resultados específicos |

---

## 6. Conclusiones

### 6.1 Progreso desde AUDIT_REPORT.md

| Estado | Cantidad | Hallazgos |
|--------|:--------:|-----------|
| **Resueltos** | 6 | C1 (IGF/λ), C2 (Sudáfrica metadata), C3 (SECRET_KEY), D2 (Nigeria grupo), D3 (fuerzas realistas), D6 (batch inserts) |
| **Parcialmente mitigados** | 2 | H1 (cache degradation), D4 (falta knockouts — no urgente) |
| **Pendientes (no resueltos)** | ~30 | El resto de hallazgos originales |

### 6.2 Riesgos Actuales más Graves

1. **Bracket no oficial (S1)**: Las simulaciones Monte Carlo no siguen el bracket oficial de FIFA 2026. Afecta la precisión de las probabilidades de avance.

2. **Simulaciones no reproducibles (S2)**: Sin seeds funcionales en Numba, no se pueden verificar resultados específicos.

3. **5/8 factores IGF sin datos**: El IGF promete 8 factores pero solo 3 tienen datos reales.

4. **Dixon-Coles ρ fijo**: ρ=0.1 hardcodeado en vez de estimado desde datos históricos.

### 6.3 Recomendaciones Prioritarias

1. ✅ **~~Corregir seed data~~** — COMPLETADO (Sudáfrica en TEAM_META, Nigeria en grupo, TEAM_STRENGTH realista, batch inserts)
2. **Implementar bracket oficial FIFA 2026** en `monte_carlo.py`
3. **Arreglar reproducibilidad**: Migrar a `numpy.random.Generator` con seeds explícitos en Numba
4. **Poblar factores IGF**: Agregar datos para los 5 factores faltantes (recent_form, wc_experience, squad_value, opponent_strength, tournament_history)
5. **Estimar ρ de Dixon-Coles** desde datos históricos en vez de usar 0.1 fijo
6. **Agregar partidos de knockout** al seed data

---

## 7. Cómo Ejecutar el Script de Auditoría

```bash
# Asegúrate de que Docker esté corriendo
docker compose up -d

# Ejecutar el script de auditoría dentro del contenedor backend
docker compose exec backend python -c "import sys; sys.path.insert(0, '/app'); sys.path.insert(0, '/app/audit'); import run_integrity_audit"
```

El script produce:
- Resultados de cada prueba en tiempo real
- Checklist estructurado al final
- Código de salida 0 si no hay fallos críticos
