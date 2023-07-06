# FastWS

<p align="center">
 <a href="https://github.com/endrekrohn/fastws">
    <img src="https://raw.githubusercontent.com/endrekrohn/fastws/assets/assets/fastws.png" alt="FastWS"/>
</a>
</p>

**Source Code**: <a href="https://github.com/endrekrohn/fastws" target="_blank">https://github.com/endrekrohn/fastws</a>

---

FastWS is a wrapper around FastAPI to create better WebSocket applications with auto-documentation using <a href="https://www.asyncapi.com/" target="_blank">AsyncAPI</a>, in a similar fashion as FastAPIs existing use of OpenAPI.

The current supported AsyncAPI verison is `2.4.0`. Once version `3.0.0` is released the plan is to upgrade to this standard.


## Requirements

Python 3.11+

`FastWS` uses Pydantic v2 and FastAPI.

## Installation


```console
$ pip install fastws
```


You will also need an ASGI server, for production such as <a href="https://www.uvicorn.org" class="external-link" target="_blank">Uvicorn</a> or <a href="https://github.com/pgjones/hypercorn" class="external-link" target="_blank">Hypercorn</a>.

<div class="termy">

```console
$ pip install "uvicorn[standard]"
```

</div>

## Example

### Create it

* Create a file `main.py` with:

```Python
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI
from fastws import Client, FastWS

service = FastWS()


@service.send("ping")
async def send_event_a() -> str:
    return "pong"


@asynccontextmanager
async def lifespan(app: FastAPI):
    service.setup(app)
    yield


app = FastAPI(lifespan=lifespan)


@app.websocket("/")
async def fastws_stream(client: Annotated[Client, Depends(service.manage)]):
    await service.serve(client)
```

We can look at the generated documentation at `http://localhost:<port>/asyncapi`.

<p align="center">
 <a href="https://github.com/endrekrohn/fastws">
    <img src="https://raw.githubusercontent.com/endrekrohn/fastws/assets/assets/asyncapi_example.png" alt="AsyncAPI Docs"/>
</a>
</p>

---

### Example breakdown

First we import and initialize the service.


```Python
from fastws import Client, FastWS

service = FastWS()
```

#### Define event

Next up we connect an operation (a WebSocket message) to the service, using the decorator `@service.send(...)`. We need to define the operation using a string similar to how we define an HTTP-endpoint using a path.

The operation-identificator is in this case `"ping"`, meaning we will use this string to identify what type of message we are receiving.

```Python
@service.send("ping")
async def send_event_a() -> str:
    return "pong"
```

If we want to define an `payload` for the operation we can extend the example:

```Python
from pydantic import BaseModel

class PingPayload(BaseModel):
    foo: str

@service.send("ping")
async def send_event_a(payload: PingPayload) -> str:
    return "pong"
```

An incoming message should now have the following format. (We will later view this in the generated AsyncAPI-documentation).

```json
{
    "type": "ping",
    "payload": {
        "foo": "bar"
    }
}
```
#### Connect service

Next up we connect the service to our running FastAPI application.

```Python
@asynccontextmanager
async def lifespan(app: FastAPI):
    service.setup(app)
    yield


app = FastAPI(lifespan=lifespan)


@app.websocket("/")
async def fastws_stream(client: Annotated[Client, Depends(service.manage)]):
    await service.serve(client)
```

The function `service.setup(app)` inside FastAPIs lifespan registers two endpoints
- `/asyncapi.json`, to retrieve our API definition 
- `/asyncapi`, to view the AsyncAPI documentation UI.

You can override both of these URLs when initializing the service, or set them to `None` to avoid registering the endpoints at all.

## Routing

To spread out our service we can use the `OperationRouter`-class.

```Python
# feature_1.py
from fastws import Client, OperationRouter
from pydantic import BaseModel

router = OperationRouter(prefix="user.")


class SubscribePayload(BaseModel):
    topic: str


class SubscribeResponse(BaseModel):
    detail: str
    topics: set[str]


@router.send("subscribe")
async def subscribe_to_topic(
    payload: SubscribePayload,
    client: Client,
) -> SubscribeResponse:
    client.subscribe(payload.topic)
    return SubscribeResponse(
        detail=f"Subscribed to {payload.topic}",
        topics=client.topics,
    )
```

We can then include the router in our main service.

```Python
# main.py
from fastws import Client, FastWS

from feature_1 import router

service = FastWS()
service.include_router(router)
```

## Operations, `send` and `recv`

The service enables two types of operations. Let us define these operations clearly:

- `send`: An operation where API user sends a message to the API server.
  
  **Note**: Up to AsyncAPI version `2.6.0` this refers to a `publish`-operation, but is changing to `send` in version `3.0.0`.

- `recv`: An operation where API server sends a message to the API user.
  
  **Note**: Up to AsyncAPI version `2.6.0` this refers to a `subscribe`-operation, but is changing to `receive` in version `3.0.0`.


### The `send`-operation

The above examples have only displayed the use of `send`-operations.

When using the functions `FastWS.client_send(message, client)` or `FastWS.serve(client)`, we implicitly send some arguments. These keyword-arguments have the following keywords and types:

- `client` with type `fastws.application.Client` 
- `app` with type `fastws.application.FastWS`
- `payload`, optional with type defined in the function processing the message.

A `send`-operation can therefore access the following arguments:

```Python
from fastws import Client, FastWS
from pydantic import BaseModel

class Something(BaseModel):
    foo: str


class Thing(BaseModel):
    bar: str


@router.send("foo")
async def some_function(
    payload: Something,
    client: Client,
    app: FastWS,
) -> Thing:
    print(f"{app.connections=}")
    print(f"{client.uid=}")

    return Thing(bar=client.uid)
```

### The `recv`-operation

When using the function `FastWS.server_send(message, topic)`, we implicitly send some arguments. These keyword-arguments have the keywords and types:

- `app` with type `fastws.application.FastWS`
- Optional `payload` with type defined in the function processing the message.

A `recv`-operation can therefore access the following arguments:

```Python
from fastws import FastWS
from pydantic import BaseModel

class AlertPayload(BaseModel):
    message: str


@router.recv("alert")
async def recv_client(payload: AlertPayload, app: FastWS) -> str:
    return "hey there!"
```

If we want create a message on the server side we can do the following:

```Python
from fastapi import FastAPI
from fastws import FastWS

service = FastWS()
app = FastAPI()

@app.post("/")
async def alert_on_topic_foobar(message: str):
    await service.server_send(
        Message(type="alert", payload={"message": message}),
        topic="foobar",
    )
    return "ok"
```

In the example above all connections subscribed to the topic `foobar` will recieve a message the the payload `"hey there!"`.

In this way you can on the server-side choose to publish messages from anywhere to any topic. This is especially useful if you have a persistent connection to Redis or similar that reads messages from some channel and want to propagate these to your users.

## Authentication

There are to ways to tackle authentication using `FastWS`.

### By defining `auth_handler`

One way is to provide a custom `auth_handler` when initializing the service. Below is an example where the API user must provide a secret message within a timeout to authenticate.

```Python
import asyncio
import logging
from fastapi import WebSocket
from fastws import FastWS


def custom_auth(to_wait: float = 5):
    async def handler(ws: WebSocket) -> bool:
        await ws.accept()
        try:
            initial_msg = await asyncio.wait_for(
                ws.receive_text(),
                timeout=to_wait,
            )
            return initial_msg == "SECRET_HUSH_HUSH"
        except asyncio.exceptions.TimeoutError:
            logging.info("Took to long to provide authentication")

        return False

    return handler


service = FastWS(auth_handler=custom_auth())
```

### By using FastAPI dependency

If you want to use your own FastAPI dependency to handle authentication before it enters the FastWS service you will have to set `auto_ws_accept` to `False`.

```Python
import asyncio
from typing import Annotated

from fastapi import Depends, FastAPI, WebSocket, WebSocketException, status
from fastws import Client, FastWS

service = FastWS(auto_ws_accept=False)

app = FastAPI()


async def custom_dep(ws: WebSocket):
    await ws.accept()
    initial_msg = await asyncio.wait_for(
        ws.receive_text(),
        timeout=5,
    )
    if initial_msg == "SECRET_HUSH_HUSH":
        return
    raise WebSocketException(
        code=status.WS_1008_POLICY_VIOLATION,
        reason="Not authenticated",
    )


@app.websocket("/")
async def fastws_stream(
    client: Annotated[Client, Depends(service.manage)],
    _=Depends(custom_dep),
):
    await service.serve(client)
```

## Heartbeats and connection lifespan

To handle a WebSocket's lifespan FastWS tries to help you by using `asyncio.timeout()`-context managers in its `serve(client)`-function.

You can set the both:
- `heartbeat_interval`: Meaning a client needs to send a message within this time.
- `max_connection_lifespan`: Meaning all connections will disconnect when exceeding this time.

These must set during initialization:

```Python
from fastws import FastWS

service = FastWS(
    heartbeat_interval=10,
    max_connection_lifespan=300,
)
```

Both `heartbeat_interval` and `max_connection_lifespan` can be set to None to disable any restrictions. Note this is the default.

Please note that you can often also set restrictions in your ASGI-server. Applicable settings for [uvicorn](https://www.uvicorn.org/#command-line-options):
- `--ws-ping-interval` INTEGER
- `--ws-ping-timeout` INTEGER
- `--ws-max-size` INTEGER