from fastapi import APIRouter, HTTPException, Query

from app.core.cache_decorator import cached
from app.schemas.calibration_refinement import RefinementReportResponse
from app.services.calibration_refinement_service import CalibrationRefinementService

router = APIRouter(prefix="/calibration/refinement", tags=["Calibration Refinement"])

_service: CalibrationRefinementService | None = None


def get_service() -> CalibrationRefinementService:
    global _service
    if _service is None:
        _service = CalibrationRefinementService()
    return _service


@router.post("/run", response_model=RefinementReportResponse)
@cached("refinement:run")
def run_refinement(
    tournaments: list[str] | None = Query(None, description="Filter by tournaments (e.g. 2014, 2018, 2022)"),
):
    """Run full calibration refinement: reliability analysis, calibration methods, bias reduction."""
    try:
        return get_service().run_refinement(tournaments)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/results", response_model=RefinementReportResponse)
@cached("refinement:results")
def get_refinement_results():
    """Get last refinement results."""
    report = get_service().get_last_report()
    if not report:
        raise HTTPException(status_code=404, detail="No refinement results yet. POST /calibration/refinement/run first.")
    return report
