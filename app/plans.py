from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import text

router = APIRouter(prefix="/api/travel-plans", tags=["Travel plans"])


class PlanFields(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    budget: Decimal | None = Field(
        default=None, ge=0, max_digits=10, decimal_places=2
    )
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    is_public: bool = False

    @model_validator(mode="after")
    def validate_dates(self):
        if (
            self.start_date is not None
            and self.end_date is not None
            and self.end_date < self.start_date
        ):
            raise ValueError("end_date must be on or after start_date")
        return self


class PlanUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    version: int = Field(gt=0)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    budget: Decimal | None = Field(
        default=None, ge=0, max_digits=10, decimal_places=2
    )
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    is_public: bool | None = None

    @model_validator(mode="after")
    def validate_required_fields(self):
        for field in ("title", "currency", "is_public"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


def serialize_row(row):
    result = dict(row)
    for key, value in result.items():
        if isinstance(value, Decimal):
            result[key] = float(value)
    return result


def create_plan_router(engine):
    @router.post("", status_code=201)
    def create_plan(payload: PlanFields):
        values = payload.model_dump()

        with engine.begin() as connection:
            row = connection.execute(
                text("""
                    INSERT INTO travel_plans (
                        title, description, start_date, end_date,
                        budget, currency, is_public
                    )
                    VALUES (
                        :title, :description, :start_date, :end_date,
                        :budget, :currency, :is_public
                    )
                    RETURNING *
                """),
                values,
            ).mappings().one()

        return serialize_row(row)

    @router.get("/{plan_id}")
    def get_plan(plan_id: UUID):
        with engine.begin() as connection:
            # Keep the plan and locations consistent while reading them.
            row = connection.execute(
                text("""
                    SELECT * FROM travel_plans
                    WHERE id = :id
                    FOR SHARE
                """),
                {"id": plan_id},
            ).mappings().first()

            if row is None:
                raise HTTPException(404, "Travel plan not found")

            locations = connection.execute(
                text("""
                    SELECT * FROM locations
                    WHERE travel_plan_id = :id
                    ORDER BY visit_order, id
                """),
                {"id": plan_id},
            ).mappings().all()

            result = serialize_row(row)
            result["locations"] = [
                serialize_row(location) for location in locations
            ]

        return result

    @router.put("/{plan_id}")
    def update_plan(plan_id: UUID, payload: PlanUpdate):
        changes = payload.model_dump(exclude_unset=True)
        expected_version = changes.pop("version")

        # Column names come exclusively from validated model fields.
        assignments = [f"{field} = :{field}" for field in changes]
        assignments.append("version = version + 1")

        statement = text(
            "UPDATE travel_plans SET "
            + ", ".join(assignments)
            + " WHERE id = :id AND version = :expected_version"
            + " RETURNING *"
        )

        with engine.begin() as connection:
            row = connection.execute(
                statement,
                {
                    **changes,
                    "id": plan_id,
                    "expected_version": expected_version,
                },
            ).mappings().first()

            if row is None:
                current_version = connection.execute(
                    text("""
                        SELECT version
                        FROM travel_plans
                        WHERE id = :id
                    """),
                    {"id": plan_id},
                ).scalar_one_or_none()

                if current_version is None:
                    raise HTTPException(404, "Travel plan not found")

                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": (
                            "Conflict: travel plan was modified; "
                            "reload it and retry with the current version"
                        ),
                        "current_version": current_version,
                    },
                )

        return serialize_row(row)

    @router.delete("/{plan_id}", status_code=204)
    def delete_plan(plan_id: UUID):
        with engine.begin() as connection:
            deleted = connection.execute(
                text("""
                    DELETE FROM travel_plans
                    WHERE id = :id
                    RETURNING id
                """),
                {"id": plan_id},
            ).first()

            if deleted is None:
                raise HTTPException(404, "Travel plan not found")

        return Response(status_code=204)

    return router