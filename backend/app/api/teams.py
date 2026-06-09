import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.cache_decorator import cached
from app.core.dependencies import PaginationParams, get_db
from app.schemas.team import TeamCreate, TeamResponse, TeamUpdate, TeamWithStats
from app.services.team_service import TeamService

router = APIRouter(prefix="/teams", tags=["Teams"])


@router.get("", response_model=list[TeamResponse])
@cached("teams:list")
def list_teams(
    pagination: PaginationParams = Depends(),
    db: Session = Depends(get_db),
):
    service = TeamService(db)
    return service.get_all(skip=pagination.offset, limit=pagination.limit)


@router.get("/{team_id}", response_model=TeamResponse)
@cached("teams:detail")
def get_team(team_id: uuid.UUID, db: Session = Depends(get_db)):
    service = TeamService(db)
    team = service.get_by_id(team_id)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


@router.post("", response_model=TeamResponse, status_code=201)
def create_team(data: TeamCreate, db: Session = Depends(get_db)):
    service = TeamService(db)
    return service.create(data)


@router.patch("/{team_id}", response_model=TeamResponse)
def update_team(team_id: uuid.UUID, data: TeamUpdate, db: Session = Depends(get_db)):
    service = TeamService(db)
    team = service.update(team_id, data)
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


@router.delete("/{team_id}", status_code=204)
def delete_team(team_id: uuid.UUID, db: Session = Depends(get_db)):
    service = TeamService(db)
    if not service.delete(team_id):
        raise HTTPException(status_code=404, detail="Team not found")
