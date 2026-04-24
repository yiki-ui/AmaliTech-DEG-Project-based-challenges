import asyncio
import logging
from fastapi import FastAPI, HTTPException
from models import CreateMonitorRequest, MonitorStatus
from store import Monitor, monitors

# basic logging so we can see what's happening in the terminal
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("watchdog")

app = FastAPI(title="Pulse Check API Watchdog Sentinel")


async def run_countdown(monitor_id: str):
    # wait for the timeout duration — if a heartbeat cancels this task we never reach the end
    monitor = monitors.get(monitor_id)
    if not monitor:
        return

    await asyncio.sleep(monitor.timeout)

    # re-fetch in case state changed while we were sleeping
    monitor = monitors.get(monitor_id)
    if not monitor or monitor.status == MonitorStatus.paused:
        return

    # timer expired naturally — device is considered down
    monitor.status = MonitorStatus.down
    logger.critical(f"Monitor '{monitor_id}' timed out.")


@app.post("/monitors", status_code=201) #201 status code: indicates that the request has been successfully fulfilled
async def register_monitor(body: CreateMonitorRequest):
    if body.id in monitors:
        raise HTTPException(
            status_code=409,
            detail=f"Monitor '{body.id}' already exists."
        )

    monitor = Monitor(id=body.id, timeout=body.timeout, alert_email=body.alert_email)
    monitors[body.id] = monitor

    # kick off the countdown as a background task
    monitor.timer_task = asyncio.create_task(run_countdown(body.id))
    logger.info(f"Monitor '{body.id}' registered. Countdown: {body.timeout}s.")

    return {
        "message": f"Monitor '{body.id}' registered. Countdown started for {body.timeout}s.",
        "id": body.id,
        "status": monitor.status,
    }