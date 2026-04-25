# setting up data models for the system

from pydantic import BaseModel 
from enum import Enum

class MonitorStatus(str, Enum):

    """
    represents the lifecycle states of a monitor.

    - active: timer is runnning, device is healthy
    - down:   timer expired, alert has been fired
    - paused: timer is stopped, no alerts will fire

    """
    active = "active"
    down = "down"
    pause = "paused"

class CreateMonitorRequest(BaseModel):
    """
    Request body for registering a new monitor.
    - id:          unique identifier for the device
    - timeout:     countdown duration in seconds before alert fires
    - alert_email: email address to notify when device goes down

    """
    id: str
    timeout: int
    alert_email: str