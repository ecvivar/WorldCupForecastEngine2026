# Hoja de Ruta — Consistencia de Predicciones y Estadísticas

Basado en los hallazgos de `INTEGRITY_AUDIT_REPORT.md`, `AUDIT_REPORT.md` y `STATISTICAL_AUDIT_REPORT.md`.

---

## Fase 1: Corrección de Datos Semilla (Prioridad Máxima)

> Sin datos realistas, cualquier mejora en los algoritmos es irrelevante.

| # | Tarea | Archivos | Detalle |
|---|-------|----------|---------|
| 1.1 | **Agregar "Sudáfrica" a `TEAM_META`** | `scripts/seed_data.py:34-83` | `"Sudáfrica": ("RSA", "Africa", 1992)` — elimina el único FAIL de la auditoría |
| 1.2 | **Asignar Nigeria a un grupo o quitarla** | `scripts/seed_data.py:19-32` | Nigeria está en `TEAM_META` pero no en `OFFICIAL_GROUPS`. Moverla al grupo que corresponda o eliminarla |
| 1.3 | **Reemplazar fuerzas arbitrarias por datos reales** | `scripts/seed_data.py:117-142` | Actualmente: `1500 + (48-i)*20` para Elo, `1800 - i*15` para FIFA. Reemplazar con valores reales de ranking FIFA/Diciembre 2025 |
| 1.4 | **Poblar los 5 factores IGF faltantes** | `scripts/seed_data.py` | Agregar columnas `recent_form`, `wc_experience`, `squad_value`, `opponent_strength`, `tournament_history` al seed. Actualmente solo Elo/xG/FIFA rank tienen datos |
| 1.5 | **Agregar partidos de knockout al seed** | `scripts/seed_data.py:174-191` | Para un torneo `group_plus_knockout`, los 72 partidos de grupo + 32 de knockout deberían existir |
| 1.6 | **Batch inserts en seed** | `scripts/seed_data.py` | Reemplazar 48 `db.flush()` individuales por `db.bulk_save_objects()` |

**Criterio de éxito:** `pytest` + auditoría muestran Sudáfrica con metadata correcta, Nigeria con grupo asignado, IGF con >3 factores activos.

---

## Fase 2: Consistencia del Pipeline IGF

> Unificar la métrica de fuerza para que predicciones de partido y Monte Carlo usen exactamente el mismo valor.

| # | Tarea | Archivos | Detalle |
|---|-------|----------|---------|
| 2.1 | **Verificar que `igf_score` se calcula una sola vez por request** | `match_service.py:51-86`, `simulation_service.py:118-119` | Ambos servicios llaman `IGFEngine.compute_team_scores()`. Extraer a un servicio compartido con cache de request |
| 2.2 | **Eliminar la dependencia del orden de iteración en IGF** | `igf.py:103-109` | La normalización min-max depende del orden de inserción. Usar percentiles o z-score en su lugar |
| 2.3 | **Agregar validación de rango en `compute_team_scores`** | `igf.py:116-135` | Asegurar que `igf_score` devuelva siempre 0-100 inclusive |
| 2.4 | **Test de integración IGF cross-service** | Nuevo test | Verificar que `MatchService`, `SimulationService` y `RankingService` produzcan IGF scores idénticos para el mismo equipo |

**Criterio de éxito:** Mismo equipo → mismo `igf_score` sin importar qué servicio lo calcule. IGF estable contra reordenamientos del dataset.

---

## Fase 3: Mejora de la Calidad Predictiva

> Los algoritmos son correctos matemáticamente pero mejorables en precisión.

| # | Tarea | Archivos | Detalle |
|---|-------|----------|---------|
| 3.1 | **Implementar Dixon-Coles completo** | `match_prediction.py:289-298` | Reemplazar el ajuste plano de 4 scores por la función τ continua: `τ(x,y;λ,μ) = 1 + ρ·((x-λ)(y-μ))/√(λμ)` |
| 3.2 | **Estimar ρ de Dixon-Coles desde datos** | `calibration.py` | En vez de ρ=0.1 fijo, estimar desde los 192 partidos históricos maximizando verosimilitud |
| 3.3 | **Mejorar Confidence Index** | `match_prediction.py` | Actualmente solo usa diferencial de rating. Incorporar varianza del modelo y tamaño de muestra histórica |
| 3.4 | **Incrementar `max_goals` a 15** | `match_prediction.py:27` | 10 es bajo para equipos muy desiguales (México-Panamá tiene λ=5.73). 15 captura >99.99% de probabilidad |
| 3.5 | **Calibrar home advantage** | `match_prediction.py:30`, `calibration.py` | Decidir: +0.08 en log-λ (Poisson) ≈ +8% goles. +100 Elo ≈ +25%. Unificar el valor |

**Criterio de éxito:** Brier score < 0.20 en históricos (vs 0.52 actual). Accuracy > 60%. Dixon-Coles implementado correctamente.

---

## Fase 4: Reproducibilidad del Monte Carlo

> Sin reproducibilidad, no se pueden verificar ni depurar resultados.

| # | Tarea | Archivos | Detalle |
|---|-------|----------|---------|
| 4.1 | **Migrar RNG de Numba a `numpy.random.Generator`** | `monte_carlo.py` | Reemplazar `np.random.seed()` por `np.random.default_rng(seed)` y pasar el generator a las funciones `@njit` |
| 4.2 | **Aceptar `seed` en `SimulationConfig`** | `domain/entities.py` | Agregar campo `seed: int | None` a `SimulationConfig` |
| 4.3 | **Propagar `seed` a `run_single_tournament_py`** | `monte_carlo.py:225-237` | Usar `seed` (si está presente) para inicializar el RNG controlado |
| 4.4 | **Test de reproducibilidad** | Nuevo test | Misma semilla → mismos resultados (verificar con 10 equipos, 100 sims) |

**Criterio de éxito:** `run(seed=42)` produce exactamente los mismos resultados cada vez.

---

## Fase 5: Bracket Oficial FIFA 2026

> El bracket actual es secuencial y no refleja el formato real del torneo.

| # | Tarea | Archivos | Detalle |
|---|-------|----------|---------|
| 5.1 | **Implementar matriz de emparejamientos FIFA 2026** | `monte_carlo.py:296-321` | Reemplazar `winner[n] vs runner_up[n]` por los cruces oficiales: 1A vs 3C/D/E, 1B vs 3A/C/D, etc. |
| 5.2 | **Mantener consistencia entre grupos y cruces** | `monte_carlo.py` | Los 12 grupos (A-L) tienen cruces fijos predefinidos en R32. Documentar la matriz oficial |
| 5.3 | **Test de bracket** | Nuevo test | Verificar que cada simulación produzca 32 equipos en R32 con emparejamientos válidos |

**Criterio de éxito:** Los cruces de R32 siguen la matriz oficial de FIFA 2026. Documentado con referencia.

---

## Fase 6: Calibración Robusta

> La calibración debe reflejar condiciones reales de partido.

| # | Tarea | Archivos | Detalle |
|---|-------|----------|---------|
| 6.1 | **Home advantage en calibración** | `calibration.py:36-48` | Asegurar que `home_advantage=True` sea el default en `calibrate()`. Ya se usa en `engine.calibrate(..., home_advantage=True)` |
| 6.2 | **Isotonic Regression serializable** | `calibration_refinement.py` | Reemplazar almacenamiento de datos crudos por modelo sklearn serializable (joblib/pickle) |
| 6.3 | **Platt Scaling con regularización** | `calibration_refinement.py` | Usar `C=1.0` con búsqueda de grid en vez de `C=1e6` |
| 6.4 | **Pipeline de calibración automática** | Nuevo servicio | Ejecutar calibración post-seed y guardar ajustes en BD para aplicarlos en predicciones |

**Criterio de éxito:** Modelos de calibración serializables, Brier < 0.18, ECE < 0.05.

---

## Fase 7: Monitoreo y Alertas

> Medir la calidad predictiva en producción.

| # | Tarea | Archivos | Detalle |
|---|-------|----------|---------|
| 7.1 | **Métrica de Brier score en `/metrics`** | `metrics.py` | Exponer `prediction_brier_score`, `prediction_accuracy` como gauge de Prometheus |
| 7.2 | **Log de predicciones** | `middleware.py` | Registrar cada predicción: equipos, probabilidades, resultado real (cuando esté disponible) |
| 7.3 | **Alerta si Brier > 0.25** | `alerts.py` | Si el Brier score semanal supera 0.25, notificar al equipo |

**Criterio de éxito:** Dashboard de calidad predictiva en `/metrics`. Alertas configuradas.

---

## Resumen de Esfuerzo

| Fase | Prioridad | Días est. | Dependencias |
|------|:---------:|:---------:|--------------|
| 1. Datos semilla | 🔴 Alta | 2-3 | Ninguna |
| 2. Consistencia IGF | 🔴 Alta | 1-2 | Fase 1 |
| 3. Calidad predictiva | 🟡 Media | 3-5 | Fase 2 |
| 4. Reproducibilidad MC | 🟡 Media | 2-3 | Ninguna |
| 5. Bracket FIFA | 🟡 Media | 2-3 | Fase 4 |
| 6. Calibración | 🟢 Baja | 2-3 | Fase 3 |
| 7. Monitoreo | 🟢 Baja | 1-2 | Fase 3 |
| **Total** | | **13-21 días** | |

## Impacto Esperado

| Métrica | Actual (Phase 10.1) | Objetivo Post-Fases 1-3 |
|---------|:-------------------:|:-----------------------:|
| IGF factores activos | 3/8 | 8/8 |
| Accuracy (últimos 20 históricos) | 65% | >65% |
| Brier Score | 0.52 | <0.20 |
| Diferencia IGF entre servicios | 0 equipos | 0 equipos |
| Reproducibilidad MC | ❌ No | ✅ Sí |
| Bracket FIFA 2026 | ❌ Secuencial | ✅ Oficial |
| Sudáfrica metadata | ❌ None/Unknown | ✅ RSA/Africa |
