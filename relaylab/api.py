from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import store


class EventInput(BaseModel):
    id: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")
    event_type: str = Field(min_length=1, max_length=100)
    payload: dict


def create_app(db=store.DEFAULT_DB):
    @asynccontextmanager
    async def lifespan(app):
        store.initialize(db)
        yield

    app = FastAPI(title="RelayLab", version="0.1.0", lifespan=lifespan)

    @app.get("/", include_in_schema=False)
    def dashboard():
        return FileResponse(Path(__file__).with_name("dashboard.html"))

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/events", status_code=201)
    def submit(event: EventInput, response: Response):
        try:
            created = store.accept_event(db, event.id, event.event_type, event.payload)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if not created:
            response.status_code = 200
        return {"created": created, "event": store.get_event(db, event.id)}

    @app.get("/events")
    def events(limit: int = Query(default=50, ge=1, le=100)):
        return store.list_events(db, limit)

    @app.get("/events/{event_id}")
    def event_details(event_id: str):
        event = store.get_event(db, event_id)
        if event is None:
            raise HTTPException(status_code=404, detail="Event not found")
        return event

    return app


app = create_app()
