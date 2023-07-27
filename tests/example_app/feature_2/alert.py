import logging
from fastws import OperationRouter
from pydantic import BaseModel

router = OperationRouter(prefix="feature_2.")


class AlertPayload(BaseModel):
    message: str


@router.recv("alert")
async def alert_from_server(payload: AlertPayload) -> AlertPayload:
    logging.info(f"{payload.message}")
    return payload
