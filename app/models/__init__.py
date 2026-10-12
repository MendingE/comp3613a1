"""Database table models.

Import every table model here so ``SQLModel.metadata.create_all`` sees them.
"""

from app.models.user import User
from app.models.alumnus import Alumnus
from app.models.event import Administrator, Event, EventRegistration

__all__ = ["User", "Alumnus", "Administrator", "Event", "EventRegistration"]
