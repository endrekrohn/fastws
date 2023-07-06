from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI
from fastws import Client, FastWS

service = FastWS()


@service.send("ping")
async def send_event_a(client: Client, app: FastWS) -> str:
    print(f"{client=}")
    print(f"{app.connections=}")

    return "pong"


@asynccontextmanager
async def lifespan(app: FastAPI):
    service.setup(app)
    yield


app = FastAPI(lifespan=lifespan)


@app.websocket("/")
async def fastws_stream(client: Annotated[Client, Depends(service.manage)]):
    await service.serve(client)
