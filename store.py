import asyncio
from datetime import datetime
from typing import Dict, Optional
from models import MonitorStatus


class Monitor:
    # tracks everything about a single registered device
    def __init__(self, id: str, timeout: int, alert_email: str):
        self.id = id
        self.timeout = timeout          # in seconds
        self.alert_email = alert_email
        self.status: MonitorStatus = MonitorStatus.active
        self.created_at: datetime = datetime.utcnow()
        self.last_heartbeat: Optional[datetime] = None
        self.timer_task: Optional[asyncio.Task] = None      # the asyncio countdown
        self.escalation_task: Optional[asyncio.Task] = None # re-alert loop if device stays down
        self.history: list = []                             # audit trail of all events

    def log_event(self, event: str):
        # stamp every state change so we have a full timeline later
        self.history.append({
            "event": event,
            "timestamp": datetime.utcnow().isoformat()
        })

    def cancel_tasks(self):
        # stop the timer before resetting or pausing
        if self.timer_task and not self.timer_task.done():
            self.timer_task.cancel()
        # also kill the escalation loop if it's running
        if self.escalation_task and not self.escalation_task.done():
            self.escalation_task.cancel()
            self.escalation_task = None


# all monitors live here, keyed by device id
monitors: Dict[str, Monitor] = {}