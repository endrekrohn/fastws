import logging
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Query
from pydantic import BaseModel

from fastws import Client, FastWS, Message


logging.basicConfig(level=logging.INFO)


service = FastWS()


@service.send("ping", reply="pong")
async def ping(client: Client, app: FastWS):
    logging.info(f"{client=} | {app.connections=}")


@service.send("no_reply")
def no_reply():
    logging.info("No reply should be sent")


class Payload(BaseModel):
    job_id: str


class Result(BaseModel):
    name: str


@service.send("work", reply="result")
async def send_work(payload: Payload) -> Result:
    logging.info(f"{payload.job_id=}")
    return Result(name="ok")


@service.recv("alert")
async def alert_from_server(app: FastWS, payload: Payload) -> Result:
    logging.info(f"{app.connections=} | {payload.job_id=}")
    return Result(name="ok")


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
        Message(type="alert", payload={"job_id": "foobar"}),
        topic=to_topic,
    )
