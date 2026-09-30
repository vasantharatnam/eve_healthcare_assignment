from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.catalogue_schemas import CentreResponse, OfferingResponse
from app.core.dependencies import get_db
from app.models.entities import (
     Centre,
     CentreTestOffering,
     DiagnosticTest,
)


router  = APIRouter(tags=["Catalogue"])

@router.get("/centres", response_model=list[CentreResponse])
def list_centres(
    db: Annotated[Session, Depends(get_db)],
) -> list[CentreResponse]:
    centres = db.scalars(
        select(Centre).order_by(Centre.name, Centre.id)
    ).all()

    return [
        CentreResponse(
            id = centre.id,
            name = centre.name,
            address = centre.address,
        )
        for centre in centres
    ]

@router.get("/centres/{centre_id}/tests" , response_model=list[OfferingResponse],)
def list_centre_tests(
    centre_id: int,
    db: Annotated[Session , Depends(get_db)],
) -> list[OfferingResponse]:
    if db.get(Centre, centre_id) is None:
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail = "Centre not found"
        )

    rows = db.execute(
        select(CentreTestOffering, DiagnosticTest)
        .join(
            DiagnosticTest,
            CentreTestOffering.test_id == DiagnosticTest.id
        )
        .where(
            CentreTestOffering.centre_id == centre_id,
            CentreTestOffering.is_active.is_(True),
        )
    ).all()


    return [
        OfferingResponse(
            offering_id = offering.id,
            test_id = diagnostic_test.id,
            test_name = diagnostic_test.name,
            description = diagnostic_test.description,
            price = offering.price,
        )

        for offering, diagnostic_test in rows
    ]