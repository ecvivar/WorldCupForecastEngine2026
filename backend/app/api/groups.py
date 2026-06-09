import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.cache_decorator import cached
from app.core.dependencies import get_db
from app.models.group import Group
from app.models.group_standing import GroupStanding
from app.schemas.group import GroupDetail, GroupResponse, GroupStandingResponse

router = APIRouter(prefix="/groups", tags=["Groups"])


@router.get("", response_model=list[GroupResponse])
@cached("groups:list")
def list_groups(db: Session = Depends(get_db)):
    groups = db.query(Group).all()
    return groups


@router.get("/{group_id}", response_model=GroupDetail)
@cached("groups:detail")
def get_group(group_id: uuid.UUID, db: Session = Depends(get_db)):
    group = (
        db.query(Group)
        .options(joinedload(Group.standings))
        .filter(Group.id == group_id)
        .first()
    )
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    standings = []
    for s in sorted(group.standings, key=lambda x: x.position):
        standings.append(
            GroupStandingResponse(
                id=s.id,
                group_id=s.group_id,
                team_id=s.team_id,
                team_name=s.team.name if s.team else "Unknown",
                position=s.position,
                played=s.played,
                won=s.won,
                drawn=s.drawn,
                lost=s.lost,
                goals_for=s.goals_for,
                goals_against=s.goals_against,
                goal_difference=s.goal_difference,
                points=s.points,
                xg_for=s.xg_for,
                xg_against=s.xg_against,
                qualified=s.qualified,
            )
        )

    return GroupDetail(
        id=group.id,
        competition_id=group.competition_id,
        name=group.name,
        stage=group.stage,
        standings=standings,
    )
