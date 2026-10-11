"""Lunch Crew: a shared card with ajo rotation for jara. Customer routes (no login) and vendor routes (stand members only)."""

from fastapi import APIRouter

public_router = APIRouter(prefix="/public/{workspace_slug}/crew", tags=["lunch_crew"])
vendor_router = APIRouter(prefix="/stands/{workspace_slug}/crew", tags=["lunch_crew"])
