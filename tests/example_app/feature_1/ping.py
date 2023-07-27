from fastws import OperationRouter

router = OperationRouter(prefix="feature_1.")


@router.send("ping", reply="pong")
async def send_ping():
    return
