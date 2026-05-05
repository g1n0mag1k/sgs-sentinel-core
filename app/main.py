from __future__ import annotations

import hashlib

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import AuditLog, User
from app.routers import auth as auth_router
from app.routers import facilities as facilities_router
from app.routers import tenants as tenants_router
from app.schemas import ScoreRequest, ScoreResponse, DualScoreRequest, DualScoreResponse
from app.services.scoring import evaluate_dscsa_risk, score_attestation, calculate_dual_score

app = FastAPI(title="SGS-Sentinel Core", version="0.1.0")

app.include_router(auth_router.router)
app.include_router(tenants_router.router)
app.include_router(facilities_router.router)

# Define the origins that are allowed to make requests to this API
origins = [
    "https://sui-g3n3ri.me",         # Your live production site
    "http://localhost:3000",        # Common for local dev
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,           # Restricts access to your specific domains
    allow_credentials=True,          # Allows the browser to send cookies/auth headers
    allow_methods=["*"],             # Allows POST, GET, OPTIONS, etc.
    allow_headers=["*"],             # Allows Authorization and Content-Type headers
)


@app.get("/api/health")
async def health_check() -> dict[str, str]:
    """Liveness probe endpoint."""
    return {"status": "ok"}


@app.post("/api/v1/assessment/score", response_model=ScoreResponse)
async def score_assessment(
    request: ScoreRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ScoreResponse:
    """Score an EPCIS payload and write an immutable chained audit record."""
    try:
        # Evaluate technical DSCSA risk score
        score = await evaluate_dscsa_