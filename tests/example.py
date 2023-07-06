import asyncio
import logging
from typing import Annotated
from fastapi import Depends, FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from fastws.docs import get_asyncapi_html

from fastws.application import FastWS, Client
from fastws.routing import Message


def get_auth(timeout: float | None = 5):
    async def auth_handler(ws: WebSocket) -> bool:
        await ws.accept()
        try:
            initial_msg = await asyncio.wait_for(ws.receive_text(), timeout=timeout)
            return initial_msg == "secret"
        except asyncio.exceptions.TimeoutError:
            logging.info("Took to long to provide authentication")
        return False

    return auth_handler


fws = FastWS(
    servers={
        "development": {
            "url": "{domain}:{port}/{basepath}",
            "description": "The development server",
            "protocol": "ws",
            "variables": {
                "domain": {"default": "localhost"},
                "port": {"default": "8000"},
                "basepath": {"default": ""},
            },
        }
    },
)


class SubscribePayload(BaseModel):
    topic: str


class SubscribeResponse(BaseModel):
    detail: str
    topics: set[str]


@fws.send("subscribe")
async def subscribe_to_topic(
    payload: SubscribePayload, client: Client
) -> SubscribeResponse:
    client.subscribe(payload.topic)
    return SubscribeResponse(
        detail=f"Subscribed to {payload.topic}", topics=client.topics
    )


@fws.recv("alert")
async def recv_client() -> str:
    return "hello"


app = FastAPI()


@app.get("/ws/docs")
def asyncapi_html():
    return HTMLResponse(get_asyncapi_html())


@app.get("/asyncapi.json")
def asyncapi_json():
    return fws.asyncapi()


@app.websocket("/")
async def fastws_stream(client: Annotated[Client, Depends(fws.manage)]):
    await fws.client(client)


@app.post("/")
async def status(topic: str):
    await fws.server_send(Message(type="alert"), topic=topic)
    return "ok"
