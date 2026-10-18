from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from msflib.eventbus import bind_app_emitter
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from .api.api_v1.api import api_router
from .bootstrap import bootstrap_module_hooks
from .core.config import settings
from .eventbus import register_customa_hooks

app = FastAPI(title=settings.PROJECT_NAME, openapi_url=f"{settings.API_V1_STR}/openapi.json")
app_emitter = bind_app_emitter(app)
bootstrap_module_hooks(app_emitter)
register_customa_hooks(app_emitter)

# Set all CORS enabled origins
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# MSFLib auth's Google sign-in keeps its sign-in state in a signed session cookie.
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY, same_site="lax")

app.include_router(api_router, prefix=settings.API_V1_STR)

# Static location for upload files.
if settings.STORAGE_METHOD == "file":
    app.mount(
        settings.STORAGE_BASE_URL,
        StaticFiles(directory=settings.STORAGE_PATH),
        name="storage",
    )
