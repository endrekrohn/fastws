from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Query
from fastws import Client, Message

from .service import service


@asynccontextmanager
async def lifespan(app: FastAPI):
    service.setup(app)
    yield


app = FastAPI(lifespan=lifespan)


@app.websocket("/")
async def fastws_stream(
    client: Annotated[Client, Depends(service.manage)],
    topics: list[str] = Query([], alias="topic"),
):
    for t in topics:
        client.subscribe(t)
    await service.serve(client)


@app.post("/{to_topic}")
async def fastws_alert(to_topic: str):
    await service.server_send(
        Message(type="feature_2.alert", payload={"message": "foobar"}),
        topic=to_topic,
    )
