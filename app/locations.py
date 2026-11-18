from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response
from pydantic import BeforeValidator, Field, ValidationError, model_validator
from sqlalchemy import text

from app.plans import INT32_MAX, StrictInput, reject_number, serialize_row

IsoDateTime = Annotated[datetime, BeforeValidator(reject_number)]


class LocationFields(StrictInput):
    address: str | None = None
    latitude: Decimal | None = Field(
        default=None, ge=-90, le=90, decimal_places=6
    )
    longitude: Decimal | None = Field(
        default=None, ge=-180, le=180, decimal_places=6
    )
    visit_order: int | None = Field(
        default=None, gt=0, le=INT32_MAX, strict=True
    )
    arrival_date: IsoDateTime | None = None
    departure_date: IsoDateTime | None = None
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
    version: int = Field(gt=0, le=INT32_MAX, strict=True)

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

            count, max_order = plan_order_stats(connection, plan_id)
            if values["visit_order"] is None:
                values["visit_order"] = max_order + 1
            else:
                # Insert "in the middle": positions k.. move up by 1.
                check_order_range(values["visit_order"], count + 1)
                shift_range(connection, plan_id, values["visit_order"],
                            max_order, +1)

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

            # Lock the location row too, so a write that bypasses the
            # plan lock cannot change it between this check and UPDATE.
            current = connection.execute(
                text("SELECT * FROM locations WHERE id = :id FOR UPDATE"),
                {"id": location_id},
            ).mappings().first()
            if current is None:
                raise HTTPException(404, "Location not found")
            if current["version"] != expected_version:
                raise location_conflict(current["version"])

            # Check dates against both saved and incoming values.
            try:
                LocationCreate.model_validate(
                    {**current_fields(current), **changes}
                )
            except ValidationError:
                raise HTTPException(
                    400, "Validation error: invalid field combination"
                ) from None

            new_order = changes.get("visit_order")
            if new_order is not None and new_order != current["visit_order"]:
                move_location(connection, plan_id, current, new_order)

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
            ).mappings().one()

        return serialize_row(row)

    @router.delete("/api/locations/{location_id}", status_code=204)
    def delete_location(location_id: UUID):
        with engine.begin() as connection:
            plan_id = find_location_plan(connection, location_id)
            lock_plan(connection, plan_id)
            deleted = connection.execute(
                text("""
                    DELETE FROM locations WHERE id = :id
                    RETURNING visit_order
                """),
                {"id": location_id},
            ).first()
            if deleted is None:
                raise HTTPException(404, "Location not found")

            # Close the gap: 1,3,4 -> 1,2,3.
            _, max_order = plan_order_stats(connection, plan_id)
            shift_range(connection, plan_id, deleted.visit_order + 1,
                        max_order, -1)

        return Response(status_code=204)

    return router


def plan_order_stats(connection, plan_id):
    row = connection.execute(
        text("""
            SELECT COUNT(*), COALESCE(MAX(visit_order), 0)
            FROM locations WHERE travel_plan_id = :plan_id
        """),
        {"plan_id": plan_id},
    ).one()
    return row[0], row[1]


def check_order_range(order, highest):
    if order > highest:
        raise HTTPException(
            400,
            f"Validation error: visit_order must be between 1 and {highest}",
        )


def shift_range(connection, plan_id, low, high, delta):
    """Move visit_order of locations in [low, high] by delta (+1 or -1).

    The caller holds the plan lock. Rows move one at a time, starting
    from the end they move towards (descending for +1, ascending for -1),
    so each target number is already free and the non-deferrable UNIQUE
    (travel_plan_id, visit_order) is never violated mid-way. A single
    UPDATE could visit rows in any order and hit the constraint.
    The version grows because visit_order of these locations changes.
    """
    direction = "DESC" if delta > 0 else "ASC"
    ids = connection.execute(
        text(f"""
            SELECT id FROM locations
            WHERE travel_plan_id = :plan_id
              AND visit_order BETWEEN :low AND :high
            ORDER BY visit_order {direction}
        """),
        {"plan_id": plan_id, "low": low, "high": high},
    ).scalars().all()

    for location_id in ids:
        connection.execute(
            text("""
                UPDATE locations
                SET visit_order = visit_order + :delta,
                    version = version + 1
                WHERE id = :id
            """),
            {"id": location_id, "delta": delta},
        )


def move_location(connection, plan_id, current, new_order):
    """Move a location to new_order; the locations in between shift.

    Example: 1 A, 2 B, 3 C, 4 D; move D to 2 -> 1 A, 2 D, 3 B, 4 C.
    The moving row first parks on a free number (MAX + 1), then the
    neighbours shift, then the caller's UPDATE sets new_order.
    """
    count, max_order = plan_order_stats(connection, plan_id)
    check_order_range(new_order, count)
    old_order = current["visit_order"]

    connection.execute(
        text("UPDATE locations SET visit_order = :free WHERE id = :id"),
        {"free": max_order + 1, "id": current["id"]},
    )
    if new_order < old_order:
        shift_range(connection, plan_id, new_order, old_order - 1, +1)
    else:
        shift_range(connection, plan_id, old_order + 1, new_order, -1)


def location_conflict(current_version):
    return HTTPException(
        status_code=409,
        detail={
            "error": (
                "Conflict: location was modified; "
                "reload it and retry with the current version"
            ),
            "current_version": current_version,
        },
    )


def current_fields(row):
    return {
        field: row[field]
        for field in LocationCreate.model_fields
    }