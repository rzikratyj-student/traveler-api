from datetime import datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import text

from app.plans import serialize_row


class LocationFields(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    address: str | None = None
    latitude: Decimal | None = Field(
        default=None, ge=-90, le=90, decimal_places=6
    )
    longitude: Decimal | None = Field(
        default=None, ge=-180, le=180, decimal_places=6
    )
    visit_order: int | None = Field(default=None, gt=0)
    arrival_date: datetime | None = None
    departure_date: datetime | None = None
    budget: Decimal | None = Field(
        default=None, ge=0, max_digits=10, decimal_places=2
    )
    notes: str | None = None

    @model_validator(mode="after")
    def validate_dates(self):
        for value in (self.arrival_date, self.departure_date):
            if value is not None and value.utcoffset() is None:
                raise ValueError("Dates must include a time zone")

        if (
            self.arrival_date is not None
            and self.departure_date is not None
            and self.departure_date < self.arrival_date
        ):
            raise ValueError("Departure must not precede arrival")
        return self


class LocationCreate(LocationFields):
    name: str = Field(min_length=1, max_length=200)


class LocationUpdate(LocationFields):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    version: int = Field(gt=0)
    @model_validator(mode="after")
    def validate_name(self):
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("Name cannot be null")
        if "visit_order" in self.model_fields_set and self.visit_order is None:
            raise ValueError("Visit order cannot be null")
        return self


def lock_plan(connection, plan_id):
    plan = connection.execute(
        text("SELECT id FROM travel_plans WHERE id = :id FOR UPDATE"),
        {"id": plan_id},
    ).first()
    if plan is None:
        raise HTTPException(404, "Travel plan not found")


def find_location_plan(connection, location_id):
    plan_id = connection.execute(
        text("SELECT travel_plan_id FROM locations WHERE id = :id"),
        {"id": location_id},
    ).scalar_one_or_none()
    if plan_id is None:
        raise HTTPException(404, "Location not found")
    return plan_id


def create_location_router(engine):
    router = APIRouter(tags=["Locations"])

    @router.post("/api/travel-plans/{plan_id}/locations", status_code=201)
    def create_location(plan_id: UUID, payload: LocationCreate):
        values = payload.model_dump()

        with engine.begin() as connection:
            # Serialize location changes within the same plan.
            lock_plan(connection, plan_id)

            if values["visit_order"] is None:
                values["visit_order"] = connection.execute(
                    text("""
                        SELECT COALESCE(MAX(visit_order), 0) + 1
                        FROM locations WHERE travel_plan_id = :plan_id
                    """),
                    {"plan_id": plan_id},
                ).scalar_one()

            columns = list(values)
            statement = text(
                "INSERT INTO locations (travel_plan_id, "
                + ", ".join(columns)
                + ") VALUES (:plan_id, "
                + ", ".join(f":{column}" for column in columns)
                + ") RETURNING *"
            )
            row = connection.execute(
                statement, {**values, "plan_id": plan_id}
            ).mappings().one()

        return serialize_row(row)

    @router.put("/api/locations/{location_id}")
    def update_location(location_id: UUID, payload: LocationUpdate):
        changes = payload.model_dump(exclude_unset=True)
        expected_version = changes.pop("version")

        with engine.begin() as connection:
            plan_id = find_location_plan(connection, location_id)
            lock_plan(connection, plan_id)

            current = connection.execute(
                text("SELECT * FROM locations WHERE id = :id"),
                {"id": location_id},
            ).mappings().first()
            if current is None:
                raise HTTPException(404, "Location not found")
            if current["version"] != expected_version:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": (
                            "Conflict: location was modified; "
                            "reload it and retry with the current version"
                        ),
                        "current_version": current["version"],
                    },
                )
            
            # Check dates against both saved and incoming values.
            LocationCreate.model_validate({**dict(current_fields(current)), **changes})

            assignments = [
                f"{field} = :{field}" for field in changes
            ]
            assignments.append("version = version + 1")

            statement = text(
                "UPDATE locations SET "
                + ", ".join(assignments)
                + " WHERE id = :id AND version = :expected_version"
                + " RETURNING *"
            )
            row = connection.execute(
                statement,
                {
                    **changes,
                    "id": location_id,
                    "expected_version": expected_version,
                },
            ).mappings().first()

            if row is None:
                raise HTTPException(
                    409,
                    "Conflict: location was modified; reload it and retry",
                )

        return serialize_row(row)

    @router.delete("/api/locations/{location_id}", status_code=204)
    def delete_location(location_id: UUID):
        with engine.begin() as connection:
            plan_id = find_location_plan(connection, location_id)
            lock_plan(connection, plan_id)
            deleted = connection.execute(
                text("DELETE FROM locations WHERE id = :id RETURNING id"),
                {"id": location_id},
            ).first()
            if deleted is None:
                raise HTTPException(404, "Location not found")

        return Response(status_code=204)

    return router


def current_fields(row):
    return {
        field: row[field]
        for field in LocationCreate.model_fields
    }