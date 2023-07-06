import asyncio
import typing
from enum import Enum

from fastws.docs import get_asyncapi
from fastws.routing import (
    Message,
    MessageT,
    MethodT,
    NoMatchingOperation,
    Operation,
    OperationRouter,
)


async def run_handler_function(
    *,
    handler: typing.Callable[..., typing.Any],
    values: dict[str, typing.Any],
) -> typing.Any:
    if asyncio.iscoroutinefunction(handler):
        return await handler(**values)
    else:
        return handler(**values)


class Broker:
    def __init__(
        self,
        title: str = "Event Driven Broker",
        version: str = "1.0.0",
        asyncapi_version: str = "2.4.0",
        description: str | None = None,
        terms_of_service: str | None = None,
        contact: dict[str, str] | None = None,
        license_info: dict[str, str] | None = None,
        servers: dict | None = None,
    ) -> None:
        self.title = title
        self.version = version
        self.asyncapi_version = asyncapi_version
        self.description = description
        self.terms_of_service = terms_of_service
        self.contact = contact
        self.license_info = license_info
        self.servers = servers
        self.router = OperationRouter()
        self.asyncapi_schema: dict | None = None

    def include_router(
        self,
        router: OperationRouter,
        *,
        prefix: str = "",
    ):
        self.router.include_router(router, prefix=prefix)

    def send(
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
            self.router.add_route(
                operation=operation,
                handler=func,
                method="SEND",
                name=name,
                tags=tags,
                summary=summary,
                description=description,
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
            self.router.add_route(
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

    def _match_route(self, operation: str, method: MethodT) -> Operation:
        for route in self.router.routes:
            if route.matches(operation, method):
                return route
        raise NoMatchingOperation("no matching route found")

    async def __call__(
        self,
        message: Message,
        method: MethodT = "SEND",
        **params,
    ) -> MessageT | None:
        route = self._match_route(operation=message.type, method=method)
        values = route.convert_params(message=message, params=params)
        result = await run_handler_function(
            handler=route.handler,
            values=values,
        )
        return route.response_payload.model_validate(
            {"type": message.type, "payload": result}
        )

    def asyncapi(self) -> dict[str, typing.Any]:
        if not self.asyncapi_schema:
            self.asyncapi_schema = get_asyncapi(
                operations=self.router.routes,
                title=self.title,
                version=self.version,
                asyncapi_version=self.asyncapi_version,
                description=self.description,
                terms_of_service=self.terms_of_service,
                contact=self.contact,
                license_info=self.license_info,
                servers=self.servers,
            )
        return self.asyncapi_schema
