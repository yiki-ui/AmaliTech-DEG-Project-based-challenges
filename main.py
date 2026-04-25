import asyncio
import logging
from datetime import datetime
from fastapi import FastAPI, HTTPException
from alerts import escalation_loop, fire_initial_alert
from models import CreateMonitorRequest, MonitorStatus
from store import Monitor, monitors

# basic logging so we can see what's happening in the terminal
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("watchdog")

app = FastAPI(
    title="Pulse Check API Watchdog Sentinel",
    description="Dead Man's Switch API for CritMon Servers Inc.",
    version="1.0.0",
)


async def run_countdown(monitor_id: str):
    # wait for the timeout, heartbeat will cancel this task before it finishes
    monitor = monitors.get(monitor_id)
    if not monitor:
        return

    await asyncio.sleep(monitor.timeout)

    # re-fetch in case state changed while sleeping
    monitor = monitors.get(monitor_id)
    if not monitor or monitor.status == MonitorStatus.paused:
        return

    # no heartbeat came in, fire the alert
    monitor.status = MonitorStatus.down
    monitor.log_event("alert_fired")
    logger.critical(f"Monitor '{monitor_id}' timed out. Firing alert.")
    fire_initial_alert(monitor_id, monitor.alert_email)

    # start escalation — keeps re-alerting until device recovers
    monitor.escalation_task = asyncio.create_task(
        escalation_loop(monitor_id, monitor.alert_email)
    )


@app.post("/monitors", status_code=201) # 201 status code: indicates that the request is successfully fulfilled
async def register_monitor(body: CreateMonitorRequest):
    if body.id in monitors:
        raise HTTPException(
            status_code=409,
            detail=f"Monitor '{body.id}' already exists."
        )

    monitor = Monitor(id=body.id, timeout=body.timeout, alert_email=body.alert_email)
    monitor.log_event("registered")
    monitors[body.id] = monitor

    # start the countdown in the background
    monitor.timer_task = asyncio.create_task(run_countdown(body.id))
    logger.info(f"Monitor '{body.id}' registered. Countdown: {body.timeout}s.")

    return {
        "message": f"Monitor '{body.id}' registered. Countdown started for {body.timeout}s.",
        "id": body.id,
        "status": monitor.status,
    }


@app.post("/monitors/{id}/heartbeat")
async def heartbeat(id: str):
    monitor = monitors.get(id)
    if not monitor:
        raise HTTPException(status_code=404, detail=f"Monitor '{id}' not found.")

    # track if we're recovering from a down state
    was_down = monitor.status == MonitorStatus.down

    # cancel the old timer and restart it fresh
    monitor.cancel_tasks()
    monitor.status = MonitorStatus.active
    monitor.last_heartbeat = datetime.utcnow()
    monitor.log_event("recovered" if was_down else "heartbeat")
    monitor.timer_task = asyncio.create_task(run_countdown(id))
    logger.info(f"Heartbeat received for '{id}'. Timer reset to {monitor.timeout}s.")

    return {
        "message": f"Heartbeat received. Timer reset for {monitor.timeout}s.",
        "id": id,
        "status": monitor.status,
    }


@app.post("/monitors/{id}/pause")
async def pause_monitor(id: str):
    monitor = monitors.get(id)
    if not monitor:
        raise HTTPException(status_code=404, detail=f"Monitor '{id}' not found.")

    # no point pausing if already paused
    if monitor.status == MonitorStatus.paused:
        return {"message": f"Monitor '{id}' is already paused.", "id": id}

    # stop the timer, no alerts will fire until heartbeat resumes it
    monitor.cancel_tasks()
    monitor.status = MonitorStatus.paused
    monitor.log_event("paused")
    logger.info(f"Monitor '{id}' paused.")

    return {
        "message": f"Monitor '{id}' paused. Send a heartbeat to resume.",
        "id": id,
        "status": monitor.status,
    }


@app.get("/monitors/{id}")
async def get_monitor(id: str):
    # returns full status and audit trail for a single device
    monitor = monitors.get(id)
    if not monitor:
        raise HTTPException(status_code=404, detail=f"Monitor '{id}' not found.")

    return {
        "id": monitor.id,
        "status": monitor.status,
        "timeout": monitor.timeout,
        "alert_email": monitor.alert_email,
        "created_at": monitor.created_at.isoformat(),
        "last_heartbeat": monitor.last_heartbeat.isoformat() if monitor.last_heartbeat else None,
        "history": monitor.history,
    }


@app.get("/monitors")
async def list_monitors():
    # quick overview of all registered monitors
    return [
        {
            "id": m.id,
            "status": m.status,
            "timeout": m.timeout,
            "alert_email": m.alert_email,
            "created_at": m.created_at.isoformat(),
            "last_heartbeat": m.last_heartbeat.isoformat() if m.last_heartbeat else None,
        }
        for m in monitors.values()
    ]


@app.delete("/monitors/{id}", status_code=200)
async def delete_monitor(id: str):
    monitor = monitors.get(id)
    if not monitor:
        raise HTTPException(status_code=404, detail=f"Monitor '{id}' not found.")

    # cancel everything before removing
    monitor.cancel_tasks()
    del monitors[id]
    logger.info(f"Monitor '{id}' deleted.")

    return {"message": f"Monitor '{id}' has been removed.", "id": id}