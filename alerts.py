import asyncio
import json
import logging
from datetime import datetime

logger = logging.getLogger("watchdog.alerts")

# how long to wait before re-alerting if device is still down
ESCALATION_INTERVAL_SECONDS = 300


def fire_initial_alert(monitor_id: str, alert_email: str):
    # build the alert payload and print it, simulates sending an email
    alert = {
        "ALERT": f"Device {monitor_id} is down!",
        "alert_email": alert_email,
        "time": datetime.utcnow().isoformat(),
    }
    print(json.dumps(alert), flush=True)
    logger.critical(json.dumps(alert))


async def escalation_loop(monitor_id: str, alert_email: str):
    # keeps re-alerting every 5 minutes until the device comes back
    # this runs as a background task so it doesn't block anything
    from store import monitors

    count = 1
    while True:
        await asyncio.sleep(ESCALATION_INTERVAL_SECONDS)

        monitor = monitors.get(monitor_id)
        if not monitor or monitor.status != "down":
            # device recovered or was deleted, stop escalating
            break

        alert = {
            "ALERT": f"[Escalation #{count}] Device {monitor_id} is STILL down!",
            "alert_email": alert_email,
            "time": datetime.utcnow().isoformat(),
        }
        print(json.dumps(alert), flush=True)
        logger.critical(json.dumps(alert))
        monitor.log_event(f"escalation_alert_#{count}")
        count += 1