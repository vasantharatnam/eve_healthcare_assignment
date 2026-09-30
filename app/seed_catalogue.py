from decimal import Decimal

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.entities import (
    Centre,
    CentreTestOffering,
    DiagnosticTest,
)


CENTRES = [
    ("EVE Indiranagar", "12 Main Road, Indiranagar, Bengaluru"),
    ("EVE Koramangala", "80 Feet Road, Koramangala, Bengaluru"),
]

TESTS = [
    ("Complete Blood Count", "Measures blood cell counts."),
    ("Lipid Profile", "Measures cholesterol and triglycerides."),
    ("Thyroid Profile", "Measures thyroid-related hormone levels."),
]

# centre name, test name, price
OFFERINGS = [
    ("EVE Indiranagar", "Complete Blood Count", Decimal("450.00")),
    ("EVE Indiranagar", "Lipid Profile", Decimal("800.00")),
    ("EVE Indiranagar", "Thyroid Profile", Decimal("950.00")),
    ("EVE Koramangala", "Complete Blood Count", Decimal("500.00")),
    ("EVE Koramangala", "Lipid Profile", Decimal("850.00")),
]


def seed() -> None:
    with SessionLocal.begin() as db:
        centres: dict[str, Centre] = {}

        for name, address in CENTRES:
            centre = db.scalar(
                select(Centre).where(Centre.name == name)
            )
            if centre is None:
                centre = Centre(name=name, address=address)
                db.add(centre)
                db.flush()

            centres[name] = centre

        tests: dict[str, DiagnosticTest] = {}

        for name, description in TESTS:
            diagnostic_test = db.scalar(
                select(DiagnosticTest).where(DiagnosticTest.name == name)
            )
            if diagnostic_test is None:
                diagnostic_test = DiagnosticTest(
                    name=name,
                    description=description,
                )
                db.add(diagnostic_test)
                db.flush()

            tests[name] = diagnostic_test

        for centre_name, test_name, price in OFFERINGS:
            centre_id = centres[centre_name].id
            test_id = tests[test_name].id

            existing = db.scalar(
                select(CentreTestOffering).where(
                    CentreTestOffering.centre_id == centre_id,
                    CentreTestOffering.test_id == test_id,
                )
            )

            if existing is None:
                db.add(
                    CentreTestOffering(
                        centre_id=centre_id,
                        test_id=test_id,
                        price=price,
                        is_active=True,
                    )
                )

    print("Sample catalogue is ready.")


if __name__ == "__main__":
    seed()