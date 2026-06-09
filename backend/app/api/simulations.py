import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.cache_decorator import cached
from app.core.dependencies import PaginationParams, get_db
from app.schemas.simulation import (
    SimulationCreate,
    SimulationResponse,
)
from app.services.simulation_service import SimulationService

router = APIRouter(prefix="/simulations", tags=["Simulations"])


@router.get("", response_model=list[SimulationResponse])
@cached("simulations:list")
def list_simulations(
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
):
    service = SimulationService(db)
    return service.get_all(skip=pagination.offset, limit=pagination.limit)


@router.get("/{sim_id}")
@cached("simulations:detail")
def get_simulation(sim_id: uuid.UUID, db: Session = Depends(get_db)):
    service = SimulationService(db)
    sim = service.get_by_id(sim_id)
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found")

    return {
        "id": str(sim.id),
        "competition_id": str(sim.competition_id),
        "name": sim.name,
        "num_simulations": sim.num_simulations,
        "status": sim.status,
        "created_at": sim.created_at.isoformat() if sim.created_at else None,
        "completed_at": sim.completed_at.isoformat() if sim.completed_at else None,
        "results": [
            {
                "id": str(r.id),
                "team_id": str(r.team_id),
                "team_name": r.team.name if r.team else "Unknown",
                "group_name": r.group_name,
                "group_position": r.group_position,
                "reached_round_of_32": r.reached_round_of_32,
                "reached_round_of_16": r.reached_round_of_16,
                "reached_quarter_final": r.reached_quarter_final,
                "reached_semi_final": r.reached_semi_final,
                "reached_final": r.reached_final,
                "won_tournament": r.won_tournament,
                "points": float(r.points),
            }
            for r in (sim.results or [])
        ],
    }


@router.post("", response_model=SimulationResponse, status_code=201)
def create_simulation(data: SimulationCreate, db: Session = Depends(get_db)):
    service = SimulationService(db)
    return service.create(data)


@router.post("/{sim_id}/run")
def run_simulation(sim_id: uuid.UUID, db: Session = Depends(get_db)):
    service = SimulationService(db)
    sim = service.run_simulation(sim_id)
    if not sim:
        raise HTTPException(status_code=404, detail="Simulation not found")

    return {
        "id": str(sim.id),
        "competition_id": str(sim.competition_id),
        "name": sim.name,
        "num_simulations": sim.num_simulations,
        "status": sim.status,
        "created_at": sim.created_at.isoformat() if sim.created_at else None,
        "completed_at": sim.completed_at.isoformat() if sim.completed_at else None,
        "results": [
            {
                "id": str(r.id),
                "team_id": str(r.team_id),
                "team_name": r.team.name if r.team else "Unknown",
                "group_name": r.group_name,
                "group_position": r.group_position,
                "reached_round_of_32": r.reached_round_of_32,
                "reached_round_of_16": r.reached_round_of_16,
                "reached_quarter_final": r.reached_quarter_final,
                "reached_semi_final": r.reached_semi_final,
                "reached_final": r.reached_final,
                "won_tournament": r.won_tournament,
                "points": float(r.points),
            }
            for r in (sim.results or [])
        ],
    }
