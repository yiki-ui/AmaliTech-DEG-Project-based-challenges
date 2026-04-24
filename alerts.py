import json
import logging
from datetime import datetime

logger = logging.getLogger("watchdog.alerts")


def fire_initial_alert(monitor_id: str, alert_email: str):
    # build the alert payload and print it, simulates sending an email
    alert = {
        "ALERT": f"Device {monitor_id} is down!",
        "alert_email": alert_email,
        "time": datetime.utcnow().isoformat(),
    }
    print(json.dumps(alert), flush=True)
    logger.critical(json.dumps(alert))