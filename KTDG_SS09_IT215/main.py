from fastapi import FastAPI, status, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from typing import Any
from datetime import datetime, timezone
from enum import Enum

app = FastAPI()


class StandardResponse(BaseModel):
    status_code: int
    message: str
    data: Any | None = None
    error: Any | None = None
    timestampt: str
    path: str


class StatusEnum(str, Enum):
    scheduled = "scheduled"
    delayed = "delayed"
    landed = "landed"

# model input


class Flight(BaseModel):
    flight_number: str = Field(
        min_length=5, max_length=10, description="Số hiệu máy bay hợp lệ")
    destination: str = Field(min_length=1, description="Địa điểm đến")
    available_seats: int = Field(ge=1)

    @field_validator("destination")
    @classmethod
    def strip_value(cls, v: str) -> str:

        if not v.strip():
            raise ValueError("Không được để trống")
        return v.strip()


# mock data
flights_db = [
    {"id": 1, "flight_number": "VN-213", "destination": "Da Nang", "available_seats": 45,
        "status": "scheduled", "created_at": "2026-07-01T06:00:00Z"},
    {"id": 2, "flight_number": "VJ-122", "destination": "Phu Quoc",
        "available_seats": 12, "status": "scheduled", "created_at": "2026-07-01T07:30:00Z"}
]


@app.get('/flights', status_code=status.HTTP_200_OK)
async def get_flights(req: Request, status_flight: StatusEnum | None = None):

    results = list(flights_db)

    if status_flight:
        results = [f for f in results if f["status"].lower() ==
                   status_flight.lower()]

    return StandardResponse(
        status_code=200,
        message="Lấy dữ liệu thành công",
        timestampt=datetime.now(timezone.utc).isoformat(),
        data=results,
        path=req.url.path
    )


@app.post('/flights', status_code=status.HTTP_201_CREATED)
async def new_flight(req: Request, flight_req: Flight):

    # check mã trùng
    is_duplicate_flight = any(f for f in flights_db if f["flight_number"].upper(
    ) == flight_req.flight_number.upper())

    if is_duplicate_flight:
        raise HTTPException(
            status_code=400,
            detail="Mã số máy bay đã trùng"  # em lười format theo mẫu quá:))
        )

    new_flight = {
        "id": max((f["id"] for f in flights_db), default=0) + 1,
        "flight_number": flight_req.flight_number.upper(),
        "destination": flight_req.destination.title(),
        "available_seats": flight_req.available_seats,
        "status": "scheduled",
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    flights_db.append(new_flight)

    return StandardResponse(
        status_code=201,
        message="Khởi tạo chuyến bay mới thành công!",
        data=new_flight,
        timestampt=datetime.now(timezone.utc).isoformat(),
        path=req.url.path
    )


@app.delete("/flight/{flight_id}", status_code=status.HTTP_200_OK)
async def cancel_flight(req: Request, flight_id: int):

    idx = next((i for i, f in enumerate(flights_db)
               if f["id"] == flight_id), None)

    if idx is None:
        raise HTTPException(
            status_code=404,
            detail="không tìm thấy chuyến bay"
        )

    # được thì xóa
    flights_db.pop(idx)

    return StandardResponse(
        status_code=200,
        message="Xóa chuyến bay thành công!",
        timestampt=datetime.now(timezone.utc).isoformat(),
        path=req.url.path
    )
