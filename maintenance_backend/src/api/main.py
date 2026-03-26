from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routers.alerts import router as alerts_router
from src.api.routers.equipment import router as equipment_router
from src.api.routers.logs import router as logs_router
from src.api.routers.parts import router as parts_router
from src.api.routers.work_orders import router as work_orders_router
from src.core.config import get_settings

settings = get_settings()

openapi_tags = [
    {"name": "equipment", "description": "Equipment registry and threshold configuration."},
    {"name": "logs", "description": "Parameter logs/readings endpoints; auto alert creation on threshold breach."},
    {"name": "alerts", "description": "Alert center endpoints."},
    {"name": "work_orders", "description": "Work order management endpoints."},
    {"name": "parts", "description": "Spare parts inventory and reservation endpoints."},
]

app = FastAPI(
    title="Predictive Maintenance Backend",
    description="FastAPI backend for predictive maintenance alerts, work orders, and parts inventory.",
    version="1.0.0",
    openapi_tags=openapi_tags,
)

allow_origins = settings.cors_origins_list()
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins if allow_origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["system"], summary="Health check", description="Basic health check endpoint.")
def health_check():
    """Return a health check response."""
    return {"message": "Healthy"}


@app.get("/docs/usage", tags=["system"], summary="API usage notes", description="Quick usage notes for frontend integration.")
def api_usage_notes():
    """Provide quick notes about API paths used by the React frontend."""
    return {
        "frontend_expected_paths": [
            "GET /equipment",
            "POST /equipment",
            "GET /logs?equipmentId=EQ-...",
            "POST /logs",
            "GET /alerts?equipmentId=...&status=Open|Closed",
            "POST /work-orders/from-alert",
            "GET /work-orders?status=Open|Closed",
            "PATCH /work-orders/{id}",
            "POST /work-orders/{id}/close",
            "GET /parts",
            "POST /parts/reserve",
        ],
        "note": "IDs returned are UI-friendly strings (e.g., AL-1, WO-2, P-3).",
    }


app.include_router(equipment_router)
app.include_router(logs_router)
app.include_router(alerts_router)
app.include_router(work_orders_router)
app.include_router(parts_router)
