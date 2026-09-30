from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.catalogue_admin_schemas import (
    CentreCreate,
    CentreUpdate,
    OfferingCreate,
    OfferingUpdate,
    TestCreate,
    TestUpdate,
)
from app.catalogue_schemas import CentreResponse, OfferingResponse
from app.core.auth import get_current_admin
from app.core.dependencies import get_db
from app.models.entities import (
    Centre,
    CentreTestOffering,
    DiagnosticTest,
    User,
)


router = APIRouter(tags=["Catalogue management"])


def commit_or_conflict(db: Session, detail: str) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        ) from exc


def offering_response(
    offering: CentreTestOffering,
    diagnostic_test: DiagnosticTest,
) -> OfferingResponse:
    return OfferingResponse(
        offering_id=offering.id,
        test_id=diagnostic_test.id,
        test_name=diagnostic_test.name,
        description=diagnostic_test.description,
        price=offering.price,
    )


@router.post(
    "/centres",
    response_model=CentreResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_centre(
    request: CentreCreate,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(get_current_admin)],
) -> CentreResponse:
    centre = Centre(name=request.name, address=request.address)
    db.add(centre)
    db.commit()
    db.refresh(centre)

    return CentreResponse(
        id=centre.id,
        name=centre.name,
        address=centre.address,
    )


@router.patch("/centres/{centre_id}", response_model=CentreResponse)
def update_centre(
    centre_id: int,
    request: CentreUpdate,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(get_current_admin)],
) -> CentreResponse:
    centre = db.get(Centre, centre_id)
    if centre is None:
        raise HTTPException(status_code=404, detail="Centre not found")

    for field, value in request.model_dump(exclude_unset=True).items():
        if value is None:
            raise HTTPException(
                status_code=422,
                detail=f"{field} cannot be null",
            )
        setattr(centre, field, value)

    db.commit()
    db.refresh(centre)

    return CentreResponse(
        id=centre.id,
        name=centre.name,
        address=centre.address,
    )


@router.post(
    "/tests",
    status_code=status.HTTP_201_CREATED,
)
def create_test(
    request: TestCreate,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(get_current_admin)],
) -> dict:
    diagnostic_test = DiagnosticTest(**request.model_dump())
    db.add(diagnostic_test)
    commit_or_conflict(db, "Test name already exists")
    db.refresh(diagnostic_test)

    return {
        "id": diagnostic_test.id,
        "name": diagnostic_test.name,
        "description": diagnostic_test.description,
    }


@router.patch("/tests/{test_id}")
def update_test(
    test_id: int,
    request: TestUpdate,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(get_current_admin)],
) -> dict:
    diagnostic_test = db.get(DiagnosticTest, test_id)
    if diagnostic_test is None:
        raise HTTPException(status_code=404, detail="Test not found")

    for field, value in request.model_dump(exclude_unset=True).items():
        if field == "name" and value is None:
            raise HTTPException(
                status_code=422,
                detail="name cannot be null",
            )
        setattr(diagnostic_test, field, value)

    commit_or_conflict(db, "Test name already exists")
    db.refresh(diagnostic_test)

    return {
        "id": diagnostic_test.id,
        "name": diagnostic_test.name,
        "description": diagnostic_test.description,
    }


@router.post(
    "/centres/{centre_id}/tests",
    response_model=OfferingResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_offering(
    centre_id: int,
    request: OfferingCreate,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(get_current_admin)],
) -> OfferingResponse:
    if db.get(Centre, centre_id) is None:
        raise HTTPException(status_code=404, detail="Centre not found")

    diagnostic_test = db.get(DiagnosticTest, request.test_id)
    if diagnostic_test is None:
        raise HTTPException(status_code=404, detail="Test not found")

    offering = CentreTestOffering(
        centre_id=centre_id,
        test_id=request.test_id,
        price=request.price,
        is_active=True,
    )
    db.add(offering)
    commit_or_conflict(db, "This centre already offers this test")
    db.refresh(offering)

    return offering_response(offering, diagnostic_test)


@router.patch("/offerings/{offering_id}", response_model=OfferingResponse)
def update_offering(
    offering_id: int,
    request: OfferingUpdate,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(get_current_admin)],
) -> OfferingResponse:
    offering = db.get(CentreTestOffering, offering_id)
    if offering is None:
        raise HTTPException(status_code=404, detail="Offering not found")

    for field, value in request.model_dump(exclude_unset=True).items():
        if value is None:
            raise HTTPException(
                status_code=422,
                detail=f"{field} cannot be null",
            )
        setattr(offering, field, value)

    db.commit()
    db.refresh(offering)

    diagnostic_test = db.get(DiagnosticTest, offering.test_id)
    return offering_response(offering, diagnostic_test)