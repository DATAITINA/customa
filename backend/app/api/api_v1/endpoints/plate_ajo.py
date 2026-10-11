"""Plate Ajo: prepaid plates at today's price. Customer routes (no login) and vendor routes (stand members only)."""

from fastapi import APIRouter

public_router = APIRouter(prefix="/public/{workspace_slug}/ajo", tags=["plate_ajo"])
vendor_router = APIRouter(prefix="/stands/{workspace_slug}/ajo", tags=["plate_ajo"])
