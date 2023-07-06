import asyncio
import logging
from typing import AsyncGenerator, AsyncIterator, Callable, Awaitable
from uuid import uuid4
from fastapi import Request, WebSocketException, status, FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, ValidationError
from starlette.websockets import WebSocket

from fastws.routing import Message, NoMatchingOperation
from fastws.broker import Broker
from fastws.docs import get_asyncapi_html


class Client:
    def __init__(self, ws: WebSocket) -> None:
        self.ws = ws
        self.uid = uuid4().hex
        self.topics: set[str] = set()

    async def send(self, message: str) -> None:
        await self.ws.send_text(message)

    def subscribe(self, topic: str) -> None:
        if topic not in self.topics:
            self.topics.add(topic)

    def unsubscribe(self, topic: str) -> None:
        if topic in self.topics:
            self.topics.remove(topic)

    async def __aiter__(self) -> AsyncIterator[Message]:
        async for message in self.ws.iter_text():
            yield Message.model_validate_json(message)


class FastWS(Broker):
    def __init__(
        self,
        *,
        title: str = "FastWS",
        version: str = "0.0.1",
        asyncapi_version: str = "2.4.0",
        description: str | None = None,
        terms_of_service: str | None = None,
        contact: dict[str, str] | None = None,
        license_info: dict[str, str] | None = None,
        servers: dict | None = None,
        asyncapi_url: str | None = "/asyncapi.json",
        asyncapi_docs_url: str | None = "/asyncapi",
        debug: bool = False,
        heartbeat_interval: float | None = None,
        max_connection_lifespan: float | None = None,
        auth_handler: Callable[[WebSocket], Awaitable[bool]] | None = None,
        auto_ws_accept: bool = True,
    ) -> None:
        super().__init__(
            title=title,
            version=version,
            asyncapi_version=asyncapi_version,
            description=description,
            terms_of_service=terms_of_service,
            contact=contact,
            license_info=license_info,
            servers=servers,
        )
        self.connections: dict[str, Client] = {}
        self.debug = debug
        self.heartbeat_interval = heartbeat_interval
        self.shutdown_event = asyncio.Event()
        self.max_connection_lifespan = max_connection_lifespan
        self.auth_handler = auth_handler
        self.auto_ws_accept = auto_ws_accept
        self.asyncapi_url = asyncapi_url
        self.asyncapi_docs_url = asyncapi_docs_url

    def log(self, msg: str) -> None:
        if self.debug:
            logging.debug(f"{msg} ({len(self.connections)} conns)")

    def _connect(self, client: Client) -> None:
        self.connections[client.uid] = client
        self.log(f"{client} connected")

    def _disconnect(self, client: Client | str) -> Client | None:
        if isinstance(client, Client):
            client = client.uid
        return self.connections.pop(client, None)

    async def _auth(self, ws: WebSocket) -> bool:
        if self.auth_handler is None:
            if self.auto_ws_accept:
                await ws.accept()
            return True
        return await self.auth_handler(ws)

    async def manage(self, ws: WebSocket) -> AsyncGenerator[Client, None]:
        if not await self._auth(ws):
            return
        client = Client(ws)
        self._connect(client)
        try:
            yield client
        except Exception:
            self.log("unknown disconnect")
        finally:
            self._disconnect(client)

    async def broadcast(self, topic: str, message: BaseModel):
        msg = message.model_dump_json()
        async with asyncio.TaskGroup() as tg:
            for client in filter(
                lambda x: topic in x.topics,
                self.connections.values(),
            ):
                tg.create_task(client.send(msg))
                self.log(f"Sent to {client.uid}")

    async def handle_exception(
        self,
        exc: ValueError | ValidationError | NoMatchingOperation | TimeoutError,
    ):
        self.log(f"could not parse message {exc}")
        error = WebSocketException(
            code=status.WS_1006_ABNORMAL_CLOSURE, reason="Could not decode message"
        )
        if isinstance(exc, ValidationError):
            error.add_note("Could not validate payload")
        if isinstance(exc, NoMatchingOperation):
            error.add_note("No matching type")
        if isinstance(exc, TimeoutError):
            error.add_note(
                "Connection timed out. "
                + f"Heartbeat interval {self.heartbeat_interval or 'unset'}. "
                + f"Max connection lifespan {self.max_connection_lifespan or 'unset'}"
            )
        raise exc

    async def serve(self, client: Client):
        try:
            async with asyncio.timeout(
                self.heartbeat_interval
            ) as heartbeat_cm, asyncio.timeout(
                self.max_connection_lifespan,
            ):
                async for message in client:
                    if self.heartbeat_interval is not None:
                        heartbeat_cm.reschedule(
                            asyncio.get_running_loop().time() + self.heartbeat_interval
                        )
                    await self.client_send(message, client=client)
        except (ValueError, ValidationError, NoMatchingOperation, TimeoutError) as exc:
            await self.handle_exception(exc)

    async def client_send(self, message: Message, *, client: Client):
        if (
            reply := await self(message, method="SEND", client=client, app=self)
        ) is not None:
            await client.send(reply.model_dump_json())

    async def server_send(self, message: Message, *, topic: str, **params):
        if (reply := await self(message, method="RECEIVE", app=self, **params)) is None:
            return
        await self.broadcast(topic, reply)

    def setup(self, app: FastAPI) -> None:
        if self.asyncapi_url and self.asyncapi_docs_url:

            async def asyncapi_ui_html(req: Request) -> HTMLResponse:
                root_path = req.scope.get("root_path", "").rstrip("/")
                asyncapi_url = f"{root_path}{self.asyncapi_url}"
                return HTMLResponse(
                    get_asyncapi_html(
                        title=f"{self.title} - AsyncAPI UI",
                        asyncapi_url=asyncapi_url,
                    )
                )

            app.add_route(
                self.asyncapi_docs_url, asyncapi_ui_html, include_in_schema=False
            )

            async def asyncapi_json(_: Request) -> JSONResponse:
                return JSONResponse(self.asyncapi())

            app.add_route(self.asyncapi_url, asyncapi_json, include_in_schema=False)
