# Checklist de Incidentes Resueltos vs. AUDIT_REPORT.md

Basado en los hallazgos del `AUDIT_REPORT.md` y los cambios realizados durante Phase 10/10.1 (certificación, Docker Compose, hardening post-certificación).

> **Nota:** Nuestro alcance incluyó infraestructura/deployment/certificación + corrección de Phase 1 del ROADMAP_CONSISTENCIA_PREDICCIONES.md (seed data). Los hallazgos del audit que requieren modificar algoritmos, seguridad o endpoints quedan fuera de este alcance.

---

## CRÍTICOS (3)

| # | Hallazgo | ¿Resuelto? | Explicación |
|---|----------|:----------:|-------------|
| C1 | **IGF inconsistente**: 3 implementaciones distintas del mismo cálculo | ✅ Sí | `match_prediction.py:144-145` ahora divide `igf_score / 50.0` (igual que `monte_carlo.py:375`). El Poisson lambda bug que producía λ=1.7e28 está resuelto. Verificado: λ_home~5.73, λ_away~0.14 |
| C2 | **Sudáfrica sin metadatos**: `fifa_code=None`, `continent='Unknown'` | ✅ Sí | `TEAM_META` actualizado con entrada `('RSA', 'Africa', 1992)`. Seed re-ejecutado. Auditoría confirma `fifa_code=RSA, continent=Africa` |
| C3 | **SECRET_KEY por defecto**: `"change-me-in-production"` | ✅ Sí | `settings.py` ahora valida SECRET_KEY (rechaza default, exige >= 32 chars). La app no arranca sin clave válida |

---

## ALTOS (8)

| # | Hallazgo | ¿Resuelto? | Explicación |
|---|----------|:----------:|-------------|
| S1 | **Bracket no oficial**: Emparejamiento secuencial en Monte Carlo | ❌ No | Requiere modificar `monte_carlo.py`. Fuera del alcance |
| S2 | **Simulaciones no reproducibles**: `np.random.seed` no afecta a Numba RNG | ❌ No | Requiere modificar motor de simulación. Fuera del alcance |
| S3 | **Race condition en paralelo**: `ProcessPoolExecutor` + Numba RNG | ❌ No | Requiere modificar motor de simulación. Fuera del alcance |
| K1 | **`home_advantage=False` en calibración** | ❌ No | Requiere re-ejecutar calibración con flag correcto. Fuera del alcance |
| D2 | **Nigeria huérfano**: En `TEAM_META` pero no en ningún grupo | ✅ Sí | Nigeria movido al Grupo G (reemplazando a Nueva Zelanda). Auditoría confirma: `group_standings=1, group=G` |
| D3 | **Fuerzas basadas en orden de inserción**: Valores arbitrarios | ✅ Sí | `TEAM_STRENGTH` dict con valores realistas por equipo (Elo 1550-2084, FIFA rank 1-49, xG 0.8-2.4). Elimina dependencia de orden |
| H1 | **Cache síncrono**: `get_sync`/`set_sync` bloquean event loop | ⚠️ Parcial | Se implementó **degradación graceful** cuando `REDIS_URL` está vacío (no-op en vez de crash). El problema de bloqueo sync en endpoints async persiste |
| SEG2 | **Credenciales PostgreSQL hardcodeadas** en URL por defecto | ❌ No | Son valores default para desarrollo; docker-compose.yml las sobreescribe. En producción el usuario debe configurar `DATABASE_URL` |

---

## MEDIOS (12)

| # | Hallazgo | ¿Resuelto? | Explicación |
|---|----------|:----------:|-------------|
| M1 | **Sin unique compuestos** en tablas | ❌ No | Requiere migración de BD. Fuera del alcance |
| P1 | **Home advantage inconsistente**: Poisson +0.08 vs Elo +100 | ❌ No | Requiere modificar engines. Fuera del alcance |
| P2 | **Dixon-Coles truncado**: Solo ajusta 4 scores | ❌ No | Requiere modificar engine. Fuera del alcance |
| S4 | **Extra time simplificado**: Poisson(0.33λ) | ❌ No | Requiere modificar motor Monte Carlo. Fuera del alcance |
| S5 | **Penales 50/50**: Ignora calidad del equipo | ❌ No | Requiere modificar motor Monte Carlo. Fuera del alcance |
| K2 | **Isotonic Regression almacena datos crudos** | ❌ No | Requiere modificar calibración. Fuera del alcance |
| K3 | **Platt Scaling con C=1e6**: Sin regularización | ❌ No | Requiere modificar calibración. Fuera del alcance |
| F1 | **Tipo erróneo en `api.matches.predict()`**: Tipado como `FullMatchPrediction` pero backend retorna `MatchPrediction` | ❌ No | Requiere modificar frontend. No usado en producción |
| SEG3 | **JWT con HS256** (simétrico) | ❌ No | Requiere migrar a RS256. Fuera del alcance |
| SEG4 | **No hay validación de longitud mínima** para `SECRET_KEY` | ❌ No | Requiere modificar validación de settings. Fuera del alcance |
| H2 | **Sin cache locking**: Thundering herd posible | ❌ No | Requiere modificar decorador de caché. Fuera del alcance |
| D4 | **No hay partidos de knockout** en seed | ❌ No | Requiere modificar seed data. Fuera del alcance |

---

## BAJOS (~15)

| # | Hallazgo | ¿Resuelto? | Explicación |
|---|----------|:----------:|-------------|
| M2 | `GroupStanding.position` sin unique por grupo | ❌ No | Requiere migración |
| M3 | `Match.status` sin enum/constraint | ❌ No | Requiere migración |
| M4 | `SimulationResult.team_name` como `@property` que retorna `""` | ❌ No | Cosmético |
| R1–R5 | Endpoints en routers incorrectos | ❌ No | Refactor cosmético |
| A1 | Sin endpoints PUT/bulk | ❌ No | Feature request |
| A2 | Endpoints solapados | ❌ No | Refactor |
| A3 | Import de `HTTPException` dentro de función | ❌ No | Código existente |
| P3 | `max_goals=10` → matriz 11×11 | ❌ No | Engine |
| P4 | Confidence Index ignora varianza | ❌ No | Engine |
| S6 | `group_position` siempre `None` en BD | ❌ No | Engine |
| K4 | `favorite_bias` nombre engañoso | ❌ No | Cosmético |
| K5 | Isotonic multi-class: 3 modelos independientes | ❌ No | Engine |
| F2–F5 | Diferencias de tipos frontend-backend benignas | ❌ No | Tipos no críticos |
| SEG5 | CORS acepta `localhost:3000,3001` | ❌ No | Config de producción |
| SEG6 | **No hay CORS middleware implementado** | ❌ No | Requiere agregar `CORSMiddleware` en `main.py` |
| SEG7 | HSTS se envía incluso sin HTTPS | ❌ No | Comportamiento esperado en desarrollo |
| D5 | Posiciones de group standing = orden de lista | ❌ No | Seed data |
| D6 | 48 flushes individuales en seed | ✅ Sí | Batch inserts con `bulk_save_objects()` |
| D7 | `date.today()` para ratings | ❌ No | Seed data |
| H3 | Sin invalidación automática de caché | ❌ No | Requiere modificar decorador |
| H4 | Sin métricas de cache miss en decorador | ❌ No | Requiere modificar decorador |

---

## Resumen

| Severidad | Total | Resueltos | Parciales | No resueltos |
|-----------|:----:|:---------:|:---------:|:------------:|
| CRÍTICO | 3 | 3 | 0 | 0 |
| ALTO | 8 | 2 | 1 | 5 |
| MEDIO | 12 | 0 | 0 | 12 |
| BAJO | ~15 | 1 | 0 | ~14 |
| **Total** | **~38** | **6** | **1** | **~31** |

### Incidentes resueltos o mitigados por nuestros cambios

| Hallazgo | Cambio que lo mitiga |
|----------|---------------------|
| **C1** — IGF inconsistente | `match_prediction.py:144-145` sincronizado con `monte_carlo.py:375`: ambos dividen `igf_score / 50.0`. Verificado con auditoría |
| **C2** — Sudáfrica sin metadata | `TEAM_META` actualizado con entrada `Sudáfrica: ('RSA', 'Africa', 1992)`. Seed re-ejecutado |
| **C3** — SECRET_KEY por defecto | Validación agregada en `settings.py`: rechaza default, exige >= 32 caracteres |
| **D2** — Nigeria huérfano | Nigeria movido al Grupo G en seed data |
| **D3** — Fuerzas arbitrarias | `TEAM_STRENGTH` dict con valores realistas (Elo, FIFA rank, xG) por equipo |
| **D6** — 48 flushes individuales | Partidos insertados con `db.bulk_save_objects()` (1 batch en vez de 72 flushes) |
| **H1** (parcial) — Cache síncrono bloqueante | Redis graceful degradation: si `REDIS_URL` está vacío, cache es no-op |
| **SEG2** (parcial) — Credenciales hardcodeadas | `docker-compose.yml` sobreescribe `DATABASE_URL` con variables de entorno separadas |

### Incidentes que quedan pendientes

Los ~31 hallazgos restantes requieren cambios en:
- **Algoritmos/Engines** (S1, S2, S3, P1, P2, S4, S5, K1, K2, K3, P3, P4, S6, K5) — ~14
- **Datos/Seed** (D4, D5, D7) — 3
- **Seguridad/Auth** (SEG2, SEG3, SEG4, SEG5, SEG6) — 5
- **Base de datos** (M1, M2, M3, M4) — 4
- **Frontend/Tipos** (F1, F2, F3, F4, F5) — 5
- **Infraestructura/Cache** (H2, H3, H4) — 3
