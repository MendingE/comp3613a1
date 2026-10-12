from datetime import date, time

from sqlalchemy import Index, text
from sqlmodel import Field, Relationship, SQLModel


class Administrator(SQLModel, table=True):
    admin_id: int | None = Field(default=None, primary_key=True)
    first_name: str = ""
    last_name: str = ""
    email: str = ""

    # STUDENT SNIPPET START: add the administrator-to-events relationship.
    events: list["Event"] = Relationship(back_populates="administrator")
    # STUDENT SNIPPET END


class Event(SQLModel, table=True):
    event_id: int | None = Field(default=None, primary_key=True)
    admin_id: int = Field(foreign_key="administrator.admin_id")
    title: str
    description: str = ""
    event_date: date
    event_time: time
    location: str
    capacity: int = Field(gt=0)
    status: str = "Open"

    # STUDENT SNIPPET START: add the event-to-administrator relationship.
    administrator: Administrator = Relationship(back_populates="events")
    # STUDENT SNIPPET END


class EventRegistration(SQLModel, table=True):
    registration_id: int | None = Field(default=None, primary_key=True)

    alumnus_id: int = Field(foreign_key="alumnus.alumni_id", index=True)
    event_id: int = Field(foreign_key="event.event_id", index=True)
    registration_date: date = Field(default_factory=date.today)
    status: str = Field(default="Pending")

    __table_args__ = (
        Index(
            "uq_registration_active_alumnus_event",
            "alumnus_id",
            "event_id",
            unique=True,
            sqlite_where=text("status != 'Cancelled'"),
            postgresql_where=text("status != 'Cancelled'"),
        ),
    )
