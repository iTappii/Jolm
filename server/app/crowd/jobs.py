"""`crowd.aggregate` (Ш-47): hourly rebuild of `place_crowd_profile` (see `service.aggregate`)."""

import logging

from app import worker
from app.crowd import service
from app.live import clock

log = logging.getLogger("app.crowd")


@worker.register("crowd.aggregate")
async def crowd_aggregate(conn, payload: dict) -> None:
    cells = await service.aggregate(conn, clock.now())
    log.info("crowd profile rebuilt", extra={"cells": cells})
