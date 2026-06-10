import logging
import time

logger = logging.getLogger("warmup")


def warmup_numba():
    """Pre-compile Numba JIT functions by running a minimal simulation.
    
    Eliminates the first-request JIT compilation penalty so that
    production traffic sees only compiled execution.
    """
    import numpy as np
    from app.engine.monte_carlo import run_single_tournament_py

    n_teams = 8
    strengths = np.array([1.0, 0.8, 0.6, 0.4, 0.3, 0.2, 0.1, 0.05], dtype=np.float64)
    assignments = np.array([0, 0, 0, 0, 1, 1, 1, 1], dtype=np.int64)

    logger.info("Numba warm-up: compiling JIT functions...")
    start = time.perf_counter()

    for _ in range(3):
        run_single_tournament_py(strengths, assignments, n_teams)

    elapsed = (time.perf_counter() - start) * 1000
    logger.info("Numba warm-up complete in %.1fms", elapsed)


def warmup_all():
    """Run all warm-up procedures."""
    try:
        warmup_numba()
    except Exception:
        logger.warning("Numba warm-up failed (non-fatal)", exc_info=True)
