from dataclasses import dataclass
from typing import Any, Hashable, Literal, Sequence

from pydantic import BaseModel
from pydantic.json_schema import GenerateJsonSchema
from pydantic_core import CoreSchema

from fastws import asyncapi
from fastws.routing import Operation


@dataclass
class Field:
    key: Hashable
    json_mode: Literal["validation", "serialization"]
    core_schema: CoreSchema


def get_fields(
    routes: Sequence[Operation],
) -> list[Field]:
    fields: list[Field] = []
    for route in routes:
        if route.payload is not None and issubclass(route.payload, BaseModel):
            fields.append(
                Field(
                    key=route.operation,
                    json_mode="validation",
                    core_schema=route.payload.__pydantic_core_schema__,
                )
            )
        if route.response_payload is not None and issubclass(
            route.response_payload, BaseModel
        ):
            key = route.operation
            if route.method == "SEND":
                key = f"{key}_reply"
            fields.append(
                Field(
                    key=key,
                    json_mode="validation",
                    core_schema=route.response_payload.__pydantic_core_schema__,
                )
            )
    return fields


def get_messages(
    routes: Sequence[Operation],
    field_mapping: dict[tuple[Hashable, Literal["validation", "serialization"]], dict],
) -> tuple[dict[str, asyncapi.Message], list[str], list[str]]:
    messages = {}
    sub_messages = []
    pub_messages = []

    for route in routes:
        msg = asyncapi.Message(
            messageId=route.operation,
            name=route.name,
            title=" ".join(route.name.split("_")).title(),
            summary=route.summary,
            description=route.description,
            tags=[asyncapi.Tag(name=t) for t in route.tags],
        )
        if route.method == "SEND":
            key = route.operation
            pub_messages.append(key)
            messages[key] = msg.model_copy(
                update={
                    "messageId": key,
                    "payload": field_mapping.get((key, "validation"), None),
                }
            )
        if route.response_model or route.method == "RECEIVE":
            key = route.operation
            if route.method == "SEND":
                key = f"{key}_reply"
            sub_messages.append(key)
            messages[key] = msg.model_copy(
                update={
                    "messageId": key,
                    "payload": field_mapping.get((key, "validation"), None),
                }
            )
    return messages, sub_messages, pub_messages


def get_asyncapi(
    operations: Sequence[Operation],
    title: str = "Event Driven Broker",
    version: str = "1.0.0",
    asyncapi_version: str = "2.4.0",
    description: str | None = None,
    terms_of_service: str | None = None,
    contact: dict[str, str] | None = None,
    license_info: dict[str, str] | None = None,
    servers: dict | None = None,
) -> dict[str, Any]:
    output: dict[str, Any] = {"asyncapi": asyncapi_version}

    output["info"] = {
        "title": title,
        "version": version,
        "description": description or "",
        "termsOfService": terms_of_service,
        "contact": contact,
        "license": license_info,
    }
    if servers is not None:
        output["servers"] = servers

    REF_SCHEMAS_TEMPLATE = "#/components/schemas/{model}"
    REF_MESSAGES_TEMPLATE = "#/components/messages/{message}"

    schema_generator = GenerateJsonSchema(ref_template=REF_SCHEMAS_TEMPLATE)

    fields = get_fields(operations)
    field_mapping, definitions = schema_generator.generate_definitions(
        inputs=[(f.key, f.json_mode, f.core_schema) for f in fields]
    )
    messages, sub_messages, pub_messages = get_messages(operations, field_mapping)

    output["channels"] = {
        "/": {
            "publish": {
                "operationId": "sendMessage",
                "summary": "The API user can send a given message to the server.",
                "message": {
                    "oneOf": [
                        {"$ref": REF_MESSAGES_TEMPLATE.format(message=v)}
                        for v in pub_messages
                    ]
                },
            },
            "subscribe": {
                "operationId": "processMessage",
                "summary": "The API user can receive a given message from the server.",
                "message": {
                    "oneOf": [
                        {"$ref": REF_MESSAGES_TEMPLATE.format(message=v)}
                        for v in sub_messages
                    ]
                },
            },
        }
    }
    messages = {k: v.model_dump(exclude_unset=True) for k, v in messages.items()}
    output["components"] = {"schemas": definitions, "messages": messages}
    return asyncapi.AsyncAPI(**output).model_dump(by_alias=True, exclude_none=True)


def get_asyncapi_html(
    *,
    title: str = "AsyncAPI",
    asyncapi_url: str = "/asyncapi.json",
    asyncapi_js_url: str = "https://unpkg.com/@asyncapi/react-component@1.0.0-next.39/browser/standalone/index.js",
    asyncapi_css_url: str = "https://unpkg.com/@asyncapi/react-component@1.0.0-next.39/styles/default.min.css",
) -> str:
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
    <link type="text/css" rel="stylesheet" href="{asyncapi_css_url}">
    <style>
    html,
    body {{
    font-family: ui-sans-serif, system-ui, Segoe UI, Roboto, Helvetica Neue, sans-serif,
    Apple Color Emoji, Segoe UI Emoji, Segoe UI Symbol, Noto Color Emoji
    }}
    </style>
    <title>{title}</title>
    </head>
    <body>
    <div id="asyncapi"></div>
    <script src="{asyncapi_js_url}"></script>
    <script>
    AsyncApiStandalone.render({{
    schema: {{
        url: '{asyncapi_url}',
        options: {{ method: "GET", mode: "cors" }},
    }},
    config: {{
        show: {{
        sidebar: true,
        }}
    }},
    }}, document.getElementById('asyncapi'));
    </script>
    </body>
    </html>"""
    return html
