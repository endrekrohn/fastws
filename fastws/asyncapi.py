from enum import Enum

from pydantic import BaseModel


class Tag(BaseModel):
    name: str | Enum


class Message(BaseModel):
    messageId: str
    name: str
    title: str
    summary: str
    description: str
    contentType: str = "application/json"
    payload: dict | None = None
    tags: list[Tag] | None = None
    examples: list[dict] | None = None


class Operation(BaseModel):
    operationId: str
    summary: str
    message: dict


class Channel(BaseModel):
    subscribe: Operation | None = None
    publish: Operation | None = None


class Components(BaseModel):
    schemas: dict
    messages: dict[str, Message]


class ServerVariable(BaseModel):
    description: str | None = None
    default: str
    enum: list[str] | None = None
    examples: list[str] | None = None


class Server(BaseModel):
    url: str
    description: str
    protocol: str
    protocolVersion: str | None = None
    variables: dict[str, ServerVariable] | None = None


class Contact(BaseModel):
    name: str
    url: str
    email: str


class License(BaseModel):
    name: str
    url: str | None = None


class Info(BaseModel):
    title: str
    version: str
    description: str
    termsOfService: str | None = None
    contact: Contact | None = None
    license: License | None = None


class AsyncAPI(BaseModel):
    asyncapi: str = "2.4.0"
    info: Info
    servers: dict[str, Server] | None = None
    channels: dict[str, Channel]
    components: Components
    defaultContentType: str = "application/json"
    externalDocs: dict | None = None
