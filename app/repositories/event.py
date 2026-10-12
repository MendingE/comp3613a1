import logging
from datetime import date, time

from sqlalchemy import func, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlmodel import Session, select

from app.models.alumnus import Alumnus
from app.models.event import Administrator, Event, EventRegistration

logger = logging.getLogger(__name__)


class EventRepositoryError(Exception):
    pass


class EventRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_events(self, query: str = "") -> list[Event]:
        statement = select(Event).where(Event.status == "Open")
        if query:
            search = f"%{query.strip()}%"
            statement = statement.where(
                Event.title.ilike(search)
                | Event.description.ilike(search)
                | Event.location.ilike(search)
            )
        statement = statement.order_by(Event.event_date, Event.event_time)
        return list(self.db.exec(statement).all())

    def get_event_by_id(self, event_id: int) -> Event | None:
        return self.db.get(Event, event_id)

    def get_administrator_id_by_email(self, email: str) -> int | None:
        statement = select(Administrator.admin_id).where(Administrator.email == email)
        return self.db.exec(statement).one_or_none()

    def list_events_for_administrator(
        self, admin_id: int, query: str = ""
    ) -> list[Event]:
        statement = select(Event).where(Event.admin_id == admin_id)
        if query:
            search = f"%{query.strip()}%"
            statement = statement.where(
                Event.title.ilike(search)
                | Event.description.ilike(search)
                | Event.location.ilike(search)
            )
        statement = statement.order_by(Event.event_date, Event.event_time)
        return list(self.db.exec(statement).all())

    def create_event(self, event: Event) -> Event:
        try:
            self.db.add(event)
            self.db.commit()
            self.db.refresh(event)
            return event
        except SQLAlchemyError as error:
            self.db.rollback()
            logger.exception("Failed to create event")
            raise EventRepositoryError("Could not save event.") from error

    def update_event_details(
        self,
        event_id: int,
        admin_id: int,
        *,
        title: str,
        description: str,
        event_date: date,
        event_time: time,
        location: str,
        capacity: int,
    ) -> bool:
        statement = (
            update(Event)
            .where(Event.event_id == event_id, Event.admin_id == admin_id)
            .values(
                title=title,
                description=description,
                event_date=event_date,
                event_time=event_time,
                location=location,
                capacity=capacity,
            )
        )
        try:
            result = self.db.exec(statement)
            if result.rowcount != 1:
                self.db.rollback()
                return False
            self.db.commit()
            return True
        except SQLAlchemyError as error:
            self.db.rollback()
            logger.exception("Failed to update event details")
            raise EventRepositoryError("Could not save event changes.") from error

    def update_event_status(
        self, event_id: int, admin_id: int, status: str
    ) -> bool:
        try:
            if status == "Cancelled":
                cancel_registrations = (
                    update(EventRegistration)
                    .where(
                        EventRegistration.event_id == event_id,
                        EventRegistration.status != "Cancelled",
                    )
                    .values(status="Cancelled")
                )
                self.db.exec(cancel_registrations)

            update_event = (
                update(Event)
                .where(Event.event_id == event_id, Event.admin_id == admin_id)
                .values(status=status)
            )
            result = self.db.exec(update_event)
            if result.rowcount != 1:
                self.db.rollback()
                return False
            self.db.commit()
            return True
        except SQLAlchemyError as error:
            self.db.rollback()
            logger.exception("Failed to update event status")
            raise EventRepositoryError("Could not save event status.") from error

    def get_event_for_update(self, event_id: int) -> Event | None:
        statement = (
            select(Event)
            .where(Event.event_id == event_id)
            .with_for_update()
        )
        return self.db.exec(statement).one_or_none()

    def get_alumnus_id(self, user_id: int) -> int | None:
        statement = select(Alumnus.alumni_id).where(Alumnus.user_id == user_id)
        return self.db.exec(statement).one_or_none()

    def registration_count(self, event_id: int) -> int:
        statement = (
            select(func.count())
            .select_from(EventRegistration)
            .where(
                EventRegistration.event_id == event_id,
                EventRegistration.status != "Cancelled",
            )
        )
        return self.db.exec(statement).one()

    def is_registered(self, alumnus_id: int, event_id: int) -> bool:
        statement = select(EventRegistration.registration_id).where(
            EventRegistration.alumnus_id == alumnus_id,
            EventRegistration.event_id == event_id,
            EventRegistration.status != "Cancelled",
        )
        return self.db.exec(statement).first() is not None

    def create_registration(self, registration: EventRegistration) -> EventRegistration:
        try:
            self.db.add(registration)
            self.db.commit()
            self.db.refresh(registration)
            return registration
        except IntegrityError:
            self.db.rollback()
            logger.exception("Duplicate or invalid event registration")
            raise

    def list_registrations_for_alumnus(
        self, alumnus_id: int
    ) -> list[tuple[EventRegistration, Event]]:
        statement = (
            select(EventRegistration, Event)
            .join(Event, Event.event_id == EventRegistration.event_id)
            .where(EventRegistration.alumnus_id == alumnus_id)
            .order_by(Event.event_date, Event.event_time)
        )
        return list(self.db.exec(statement).all())
