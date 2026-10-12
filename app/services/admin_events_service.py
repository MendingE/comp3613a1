from datetime import date, time

from app.models.event import Event
from app.repositories.event import EventRepository


class InvalidEventStatusError(Exception):
    pass


class AdministratorNotFoundError(Exception):
    pass


class EventNotFoundError(Exception):
    pass


class EventOwnershipError(Exception):
    pass


class EventStatusUpdateConflictError(Exception):
    pass


class EventDetailsUpdateConflictError(Exception):
    pass


class InvalidEventDetailsError(Exception):
    pass


class AdminEventsService:
    ALLOWED_STATUSES = {"Open", "Closed", "Cancelled"}

    def __init__(self, repository: EventRepository):
        self.repository = repository

    def _administrator_id(self, admin_email: str) -> int:
        admin_id = self.repository.get_administrator_id_by_email(admin_email)
        if admin_id is None:
            raise AdministratorNotFoundError
        return admin_id

    @staticmethod
    def _parse_event_details(
        title: str,
        description: str,
        date_value: str,
        time_value: str,
        location: str,
        capacity_value: str,
    ) -> tuple[str, str, date, time, str, int]:
        title = title.strip()
        location = location.strip()
        if not title:
            raise InvalidEventDetailsError("Enter an event title.")
        if not location:
            raise InvalidEventDetailsError("Enter an event location.")

        try:
            event_date = date.fromisoformat(date_value)
        except ValueError as error:
            raise InvalidEventDetailsError("Enter a valid event date.") from error
        try:
            event_time = time.fromisoformat(time_value)
        except ValueError as error:
            raise InvalidEventDetailsError("Enter a valid event time.") from error
        try:
            capacity = int(capacity_value)
        except ValueError as error:
            raise InvalidEventDetailsError(
                "Capacity must be a positive whole number."
            ) from error
        if capacity <= 0:
            raise InvalidEventDetailsError(
                "Capacity must be a positive whole number."
            )

        return title, description.strip(), event_date, event_time, location, capacity

    def list_events(self, admin_email: str, query: str = "") -> list[Event]:
        admin_id = self._administrator_id(admin_email)
        return self.repository.list_events_for_administrator(admin_id, query)

    def create_event(
        self,
        admin_email: str,
        *,
        title: str,
        description: str,
        date_value: str,
        time_value: str,
        location: str,
        capacity_value: str,
    ) -> Event:
        admin_id = self._administrator_id(admin_email)
        details = self._parse_event_details(
            title, description, date_value, time_value, location, capacity_value
        )
        title, description, event_date, event_time, location, capacity = details
        return self.repository.create_event(
            Event(
                admin_id=admin_id,
                title=title,
                description=description,
                event_date=event_date,
                event_time=event_time,
                location=location,
                capacity=capacity,
            )
        )

    def update_event_details(
        self,
        event_id: int,
        admin_email: str,
        *,
        title: str,
        description: str,
        date_value: str,
        time_value: str,
        location: str,
        capacity_value: str,
    ) -> None:
        admin_id = self._administrator_id(admin_email)
        event = self.repository.get_event_by_id(event_id)
        if event is None:
            raise EventNotFoundError
        if event.admin_id != admin_id:
            raise EventOwnershipError

        details = self._parse_event_details(
            title, description, date_value, time_value, location, capacity_value
        )
        title, description, event_date, event_time, location, capacity = details
        updated = self.repository.update_event_details(
            event_id,
            admin_id,
            title=title,
            description=description,
            event_date=event_date,
            event_time=event_time,
            location=location,
            capacity=capacity,
        )
        if not updated:
            raise EventDetailsUpdateConflictError

    def update_event_status(
        self, event_id: int, admin_email: str, status: str
    ) -> None:
        if status not in self.ALLOWED_STATUSES:
            raise InvalidEventStatusError

        admin_id = self._administrator_id(admin_email)

        event: Event | None = self.repository.get_event_by_id(event_id)
        if event is None:
            raise EventNotFoundError
        if event.admin_id != admin_id:
            raise EventOwnershipError

        if not self.repository.update_event_status(event_id, admin_id, status):
            raise EventStatusUpdateConflictError
