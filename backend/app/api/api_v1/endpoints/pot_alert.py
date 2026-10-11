"""Pot Alert: tell me when my dish is ready. Customer routes (no login) and vendor routes (stand members only)."""

from fastapi import APIRouter

public_router = APIRouter(prefix="/public/{workspace_slug}/pot", tags=["pot_alert"])
vendor_router = APIRouter(prefix="/stands/{workspace_slug}/pot", tags=["pot_alert"])
