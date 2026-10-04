"""Local demonstration receiver; its receipt history is kept in memory."""
from fastapi import FastAPI, HTTPException
from .api import EventInput

app = FastAPI(title="RelayLab demo receiver")
receipts = []


@app.post("/webhook")
def receive(event: EventInput):
    receipts.append(event.model_dump())
    # Retain only the latest 100 receipts in this demonstration process.
    del receipts[:-100]
    return {"received": event.id}


@app.get("/received")
def received():
    return receipts


@app.post("/fail")
def fail():
    raise HTTPException(status_code=503, detail="Intentional demo failure")
