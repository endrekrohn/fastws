from fastws import FastWS

from .feature_0 import subscribe
from .feature_1 import ping
from .feature_2 import alert

service = FastWS(title="FastWS - Broker")

service.include_router(subscribe.router)
service.include_router(ping.router)
service.include_router(alert.router)


@service.send("ping", reply="pong")
def application_ping():
    return
