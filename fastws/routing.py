import inspect
import typing
from enum import Enum
from typing import Generic, Literal, TypeVar, Union

from fastapi.dependencies.utils import get_typed_return_annotation, get_typed_signature
from pydantic import BaseModel

MethodT = Literal["SEND", "RECEIVE"]
PayloadT = TypeVar("PayloadT")
EventTypeT = TypeVar("EventTypeT", str, int)


class _Msg(BaseModel, Generic[EventTypeT]):
    type: EventTypeT | str


class _MsgWithPayload(_Msg, Generic[EventTypeT, PayloadT]):
    payload: PayloadT | None


class Message(_MsgWithPayload, Generic[EventTypeT, PayloadT]):
    payload: PayloadT | None = None


MessageT = Union[_Msg, _MsgWithPayload]


class NoMatchingOperation(Exception):
    ...


def get_name(endpoint: typing.Callable) -> str:
    if inspect.isroutine(endpoint) or inspect.isclass(endpoint):
        return endpoint.__name__
    return endpoint.__class__.__name__


class Operation:
    def __init__(
        self,
        operation: str,
        handler: typing.Callable[..., typing.Any],
        method: MethodT,
        *,
        name: str | None = None,
        tags: list[str | Enum] | None = None,
        summary: str | None = None,
        description: str | None = None,
        reply_operation: str | None = None,
    ) -> None:
        self.operation = operation
        self.handler = handler
        self.method: MethodT = method
        self.name = get_name(handler) if name is None else name
        self.tags = tags or []
        self.summary = summary
        self.description = description or inspect.cleandoc(self.handler.__doc__ or "")
        self.description = self.description.split("\f")[0].strip()
        self.response_model = get_typed_return_annotation(self.handler)
        self.parameters = get_typed_signature(self.handler).parameters.copy()
        self.reply_operation = (
            reply_operation if self.method == "SEND" else self.operation
        )
        if self.method == "SEND" and self.response_model is not None:
            assert (
                self.reply_operation is not None
            ), "Send operations with a response model defined must include a reply"

        op_t = Literal[self.operation]  # type: ignore
        reply_t = Literal[self.reply_operation or self.operation]  # type: ignore

        self.payload = _Msg[op_t]
        self.reply_payload = _Msg[reply_t]

        if (p := self.parameters.get("payload", None)) is not None:
            self.payload = _MsgWithPayload[op_t, p.annotation]

        if self.response_model is not None:
            self.reply_payload = _MsgWithPayload[reply_t, self.response_model]

    def matches(self, operation: str, method: MethodT) -> bool:
        return self.operation == operation and self.method == method

    def convert_params(
        self,
        message: Message,
        params: dict[str, typing.Any],
    ) -> dict[str, typing.Any]:
        converted_params = {}

        for k, v in self.parameters.items():
            if k == "payload" and issubclass(v.annotation, BaseModel):
                converted_params[k] = v.annotation.model_validate(message.payload)
            else:
                if k not in params:
                    raise RuntimeError(f"Missing parameter {k} of type {v.annotation}")
                converted_params[k] = params.get(k)
        if not (self.parameters.keys() == converted_params.keys()):
            raise RuntimeError("Missing parameters in function call")
        return converted_params


class OperationRouter:
    def __init__(
        self,
        *,
        prefix: str = "",
        tags: list[str | Enum] | None = None,
        routes: list[Operation] | None = None,
    ) -> None:
        self.prefix = prefix
        self.tags = tags or []
        self.routes = routes or []

    def add_route(
        self,
        operation: str,
        handler: typing.Callable[..., typing.Any],
        method: MethodT,
        *,
        name: str | None = None,
        tags: list[str | Enum] | None = None,
        summary: str | None = None,
        description: str | None = None,
        reply_operation: str | None = None,
    ) -> None:
        existing_operations = [h.operation for h in self.routes] + [
            h.reply_operation for h in self.routes if h.reply_operation is not None
        ]
        assert (
            operation not in existing_operations
        ), f"handler with operation '{operation}' already added"
        assert (
            reply_operation not in existing_operations
        ), f"handler with operation '{reply_operation}' already added"
        current_tags = self.tags.copy()
        if tags:
            current_tags.extend(tags)
        route = Operation(
            operation=operation,
            handler=handler,
            method=method,
            name=name,
            summary=summary,
            description=description,
            tags=current_tags,
            reply_operation=reply_operation,
        )
        self.routes.append(route)

    def include_router(
        self,
        router: "OperationRouter",
        *,
        prefix: str = "",
    ):
        for route in router.routes:
            self.add_route(
                operation=f"{prefix}{router.prefix}{route.operation}",
                handler=route.handler,
                method=route.method,
                name=route.name,
                tags=route.tags,
                summary=route.summary,
                description=route.description,
            )

    def send(
        self,
        operation: str,
        name: str | None = None,
        tags: list[str | Enum] | None = None,
        summary: str | None = None,
        description: str | None = None,
        reply: str | None = None,
    ) -> typing.Callable[
        [typing.Callable[..., typing.Any]], typing.Callable[..., typing.Any]
    ]:
        def decorator(
            func: typing.Callable[..., typing.Any],
        ) -> typing.Callable[..., typing.Any]:
            self.add_route(
                operation=operation,
                handler=func,
                method="SEND",
                name=name,
                tags=tags,
                summary=summary,
                description=description,
                reply_operation=reply,
            )
            return func

        return decorator

    def recv(
        self,
        operation: str,
        name: str | None = None,
        tags: list[str | Enum] | None = None,
        summary: str | None = None,
        description: str | None = None,
    ) -> typing.Callable[
        [typing.Callable[..., typing.Any]], typing.Callable[..., typing.Any]
    ]:
        def decorator(
            func: typing.Callable[..., typing.Any],
        ) -> typing.Callable[..., typing.Any]:
            self.add_route(
                operation=operation,
                handler=func,
                method="RECEIVE",
                name=name,
                tags=tags,
                summary=summary,
                description=description,
            )
            return func

        return decorator
