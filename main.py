from fastapi import FastAPI, HTTPException, status, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, AfterValidator, field_validator
from typing import Any, Annotated
from datetime import datetime, timezone
from enum import Enum

app = FastAPI()


# dữ liệu mô phỏng

tasks_db = [
    {
        "id": 1,
        "title": "Thiet ke database Shop AI",
        "description": "Xay dung bang va toi uu index",
        "assignee": "QuyDev",
        "priority": 1,
        "status": "todo",
        "created_at": "2026-07-01T09:00:00Z"
    },
    {
        "id": 2,
        "title": "Code bo API Authen",
        "description": "Trien khai filter verify JWT token",
        "assignee": "FixerQ",
        "priority": 2,
        "status": "done",
        "created_at": "2026-07-01T10:00:00Z"
    }
]


# unified envelope (thống nhất 1 cấu trúc response trả về)

class StandardResponse(BaseModel):
    status_code: int
    message: str
    data: Any | None = None
    error: str | None = None
    timestamp: str
    path: str


# các status dc cho phép
class statusEnum(str, Enum):
    todo = "todo"
    done = "done"

# model create_new_tasks


class TaskCreateSchema(BaseModel):
    title: str = Field(min_length=3, max_length=100,
                       description="Nhập tiêu đề hợp lí")
    description: str = Field(min_length=5, description="Nhập mô tả hợp lí")
    assignee: str = Field(min_length=5, description="Nhập bên ủy thác hợp lí")
    priority: int = Field(ge=1, le=5, description="Nhập mức độ ưu tiên")
    status: statusEnum = Field(
        description="Nhập trạng thái hợp lệ (todo, done)")

    @field_validator("title", "description", "assignee")
    @classmethod
    def validate_task_strings(cls, v: str, info) -> str:

        if not v.strip():
            raise Exception()

        # ktra chuỗi phải là kí tự
        for c in v:
            if not (c.isalpha() or c.isspace()):
                raise Exception()

        return v.strip()

# Model chuyên dụng để nhận dữ liệu cập nhật trạng thái đơn lẻ (PATCH)


class TaskStatusUpdateSchema(BaseModel):
    status: statusEnum = Field(
        description="Cập nhật trạng thái mới hợp lệ (todo, done)")

# make success response


def create_success_response(req: Request, status_code: int, message: str, data: Any):
    current_time = datetime.now(timezone.utc).isoformat()
    return JSONResponse(
        status_code=status_code,
        content=StandardResponse(
            status_code=status_code,
            message=message,
            data=data,
            timestamp=current_time,
            path=req.url.path
        ).model_dump()
    )


# make fail response
def create_fail_response(req: Request, status_code: int, message: str, error: str):
    current_time = datetime.now(timezone.utc).isoformat()
    return JSONResponse(
        status_code=status_code,
        content=StandardResponse(
            status_code=status_code,
            message=message,
            error=error,
            timestamp=current_time,
            path=req.url.path
        ).model_dump()
    )


# GLOBAL EXCEPTION
@app.exception_handler(Exception)
def exception_handler(req: Request, exc: Exception):

    return create_fail_response(
        req=req,
        status_code=500,
        message="Lỗi: Dữ liệu đầu vào không hợp lệ hoặc sai định dạng quy định",
        error="ERR-VAL-422: Validation error at Request Body fields constraint layout."
    )

# Chức năng 1: Xem danh sách công việc hiện có


@app.get("/tasks", tags=["QLCV"], status_code=status.HTTP_200_OK)
def get_all_tasks(req: Request, status: str | None = None):

    results = list(tasks_db)

    if status:
        results = [t for t in tasks_db if t["status"].lower() == status]

    return create_success_response(
        req=req,
        status_code=200,
        message="Lấy danh sách công việc thành công!",
        data=results
    )


# Chức năng 2: Tạo mới công việc nhóm
@app.post("/tasks", tags=["QLCV"], status_code=status.HTTP_201_CREATED)
def new_tasks(req: Request, task_in: TaskCreateSchema):

    # check trùng tittle

    is_duplicate_title = next(
        (t for t in tasks_db if task_in.title.lower() == t.get("title", "").lower()), None)

    if is_duplicate_title:
        return create_fail_response(
            req=req,
            status_code=400,
            message="Lỗi: Tiêu đề công việc này đã tồn tại trong nhóm!",
            error="ERR-TASK-01: Task conflict: Title field duplicates an existing record."
        )

    # thành công thì thêm vào
    new_task = {
        "id": max((t["id"] for t in tasks_db), default=0) + 1,
        "title": task_in.title.title(),
        "description": task_in.description.capitalize(),
        "assignee": task_in.assignee.title(),
        "priority": task_in.priority,
        "status": task_in.status,
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    tasks_db.append(new_task)

    return create_success_response(
        status_code=200,
        message="Khởi tạo công việc mới thành công!",
        data=new_task,
        req=req
    )


# Chức năng 3: Cập nhật trạng thái tiến độ công việc (Dùng PATCH)
@app.patch("/tasks/{task_id}", tags=["QLCV"], status_code=status.HTTP_200_OK)
def update_task_status(req: Request, task_id: int, status_in: TaskStatusUpdateSchema):

    # 🔍 Bước 1: Tìm kiếm xem ID công việc có tồn tại trong hệ thống hay không
    target_task = next((t for t in tasks_db if t["id"] == task_id), None)

    # 🪤 Bẫy nghiệp vụ 01: Nếu không tìm thấy ID -> Trả về lỗi 404 hệ thống
    if target_task is None:
        return create_fail_response(
            req=req,
            status_code=status.HTTP_404_NOT_FOUND,
            message="Thất bại: Không tìm thấy công việc yêu cầu!",
            error="ERR-TASK-03: Resource Not Found: The requested task_id does not exist."
        )

    # 🪤 Bẫy nghiệp vụ 02: Nếu trạng thái hiện tại đã là "done", chặn đứng không cho phép lùi ca/chỉnh sửa
    if target_task["status"].lower() == "done":
        return create_fail_response(
            req=req,
            status_code=status.HTTP_400_BAD_REQUEST,
            message="Thất bại: Công việc đã hoàn thành, không được phép thay đổi trạng thái nữa!",
            error="ERR-TASK-04: Bad Request: Modification blocked. Completed tasks cannot change status."
        )

    # ✨ Bước 3: Thỏa mãn mọi điều kiện -> Tiến hành cập nhật trường dữ liệu duy nhất
    target_task["status"] = status_in.status.value

    # Trả về gói Envelope Response thành công theo chuẩn cấu trúc dữ liệu mẫu
    return create_success_response(
        req=req,
        status_code=200,
        message="Cập nhật tiến độ công việc thành công!",
        data=target_task
    )


# Chức năng 4: Thống kê hiệu suất và Phân bổ tài nguyên (Yêu cầu hàm tính toán có giá trị return)
@app.get("/tasks/analytics/dashboard", tags=["QLCV"], status_code=status.HTTP_200_OK)
# hàm điều hướng gọi hàm service xử lí nghiệp vụ calculate_team_metrics()
def get_dashboard_analytics(req: Request):

    return create_success_response(
        req=req,
        status_code=200,
        message="Lấy số liệu thống kê hiệu suất nhóm thành công!",
        data=calculate_team_metrics()
    )


# hàm nghiệp vụ giả định
def calculate_team_metrics():

    task_dashboard = {
        "total_tasks": len(tasks_db),
        "completed_tasks": sum(1 if t["status"] == "done" else 0 for t in tasks_db),
        "completion_rate_percentage":  float((sum(1 if t["status"] == "done" else 0 for t in tasks_db) / len(tasks_db)) * 100)
    }

    return task_dashboard
