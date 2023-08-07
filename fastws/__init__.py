"""FastWS framework. Auto-documentation WebSockets using AsyncAPI around FastAPI."""

__version__ = "0.1.7"

from .application import Client as Client
from .application import FastWS as FastWS
from .docs import get_asyncapi as get_asyncapi
from .docs import get_asyncapi_html as get_asyncapi_html
from .routing import Message as Message
from .routing import Operation as Operation
from .routing import OperationRouter as OperationRouter
