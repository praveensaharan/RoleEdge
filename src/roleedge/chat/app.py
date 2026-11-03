"""Chat playground: a local web UI to talk to any configured model and see token/cache usage.

The browser keeps the conversation and sends the full history each turn; this server forwards
it to the chosen provider. API keys never leave the server.

It also serves the product demo's data: ``/api/demo/story`` (saved outputs as one JSON, see ``story.py``),
``/api/demo/icons`` (the line-icon set from ``render/icons.py``)
and the saved cards, videos and calendars under ``/media/content``.

Run:  roleedge chat     (or: uvicorn roleedge.chat.app:create_app --factory)
"""

from __future__ import annotations

import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ..checkin import CHECKIN_DIR
from ..config import DEFAULT_AZURE_DEPLOYMENT, DEFAULT_META_MODEL, DEMO_WEB_DIR, WEB_DIR
from ..content import CONTENT_DIR
from ..llm import PROVIDER_CLASSES, Provider, ProviderError, configured_providers
from ..render.icons import ICONS
from . import story
from .schemas import ChatRequest, ChatResponse, ModelsResponse, ProviderInfo

FALLBACK_DEFAULTS = {"meta": DEFAULT_META_MODEL, "azure": DEFAULT_AZURE_DEPLOYMENT}


def create_app(providers: dict[str, Provider] | None = None, content_dir: Path = CONTENT_DIR,
               checkin_dir: Path = CHECKIN_DIR) -> FastAPI:
    """Build the app. Pass ``providers`` (and output folders) to inject fakes in tests; default is whatever .env
    configures and the real ``output/`` folder."""
    providers = configured_providers() if providers is None else providers
    app = FastAPI(title="CareCircle chat playground")
    model_list: dict[str, ModelsResponse] = {}

    @app.get("/api/models")
    def list_models(refresh: bool = False) -> ModelsResponse:
        if refresh or "value" not in model_list:
            model_list["value"] = ModelsResponse(
                providers=[ProviderInfo(id=pid, label=cls.label, efforts=list(cls.efforts),
                                        models=providers[pid].list_models() if pid in providers else [])
                           for pid, cls in PROVIDER_CLASSES.items()],
                defaults={pid: providers[pid].default_model if pid in providers else FALLBACK_DEFAULTS[pid]
                          for pid in PROVIDER_CLASSES},
            )
        return model_list["value"]

    @app.post("/api/chat")
    def chat(req: ChatRequest) -> ChatResponse:
        if not req.messages or req.messages[-1].role != "user":
            raise HTTPException(400, "Last message must be from the user.")
        provider = providers.get(req.provider)
        if provider is None:
            raise HTTPException(400, f"Provider '{req.provider}' is not configured (see .env.example).")
        if req.effort not in provider.efforts:
            raise HTTPException(400, f"Effort '{req.effort}' not supported for {req.provider}.")
        started = time.time()
        try:
            reply = provider.chat(req.to_messages(), model=req.model, effort=req.effort)
        except ProviderError as exc:
            raise HTTPException(502, str(exc)) from exc
        return ChatResponse(text=reply.text, usage=reply.usage.to_dict(), model=reply.model, note=reply.note,
                            latency_s=round(time.time() - started, 2))

    @app.get("/api/demo/story")
    def demo_story() -> dict:
        return story.build(content_dir, checkin_dir)

    @app.get("/api/demo/icons")
    def demo_icons() -> dict[str, str]:
        return ICONS  # the same line icons the cards use, so the web app has no second copy

    @app.get("/demo")
    def demo_page() -> FileResponse:
        return FileResponse(DEMO_WEB_DIR / "index.html")

    app.mount("/media/content", StaticFiles(directory=content_dir, check_dir=False), name="media")
    app.mount("/demo-static", StaticFiles(directory=DEMO_WEB_DIR, check_dir=False), name="demo-static")
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

    return app
