from dataclasses import dataclass

from app.models.event import Event, EventRegistration
from app.repositories.event import EventRepository


class ProfileRequiredError(Exception):
    pass


class EventUnavailableError(Exception):
    pass


class AlreadyRegisteredError(Exception):
    pass


@dataclass(frozen=True)
class EventCard:
    event: Event
    spaces_available: int
    is_full: bool
    already_registered: bool
    has_profile: bool
    can_register: bool


@dataclass(frozen=True)
class AlumniRegistration:
    registration: EventRegistration
    event: Event


class AlumniEventsService:
    def __init__(self, repository: EventRepository):
        self.repository = repository

    def _card(self, event: Event, user_id: int) -> EventCard:
        alumnus_id = self.repository.get_alumnus_id(user_id)
        registration_count = self.repository.registration_count(event.event_id)
        spaces_available = max(0, event.capacity - registration_count)
        is_full = event.status != "Open" or spaces_available == 0
        already_registered = (
            alumnus_id is not None
            and self.repository.is_registered(alumnus_id, event.event_id)
        )
        return EventCard(
            event=event,
            spaces_available=spaces_available,
            is_full=is_full,
            already_registered=already_registered,
            has_profile=alumnus_id is not None,
            can_register=not is_full and not already_registered and alumnus_id is not None,
        )

    def list_events(self, query: str = "", user_id: int | None = None) -> list[EventCard]:
        if user_id is None:
            raise ValueError("A signed-in user is required to list events.")
        return [
            self._card(event, user_id)
            for event in self.repository.list_events(query)
        ]

    def get_event(self, event_id: int, user_id: int) -> EventCard | None:
        event = self.repository.get_event_by_id(event_id)
        return self._card(event, user_id) if event is not None else None

    def register_for_event(self, event_id: int, user_id: int) -> EventRegistration:
        alumnus_id = self.repository.get_alumnus_id(user_id)
        if alumnus_id is None:
            raise ProfileRequiredError

        event = self.repository.get_event_for_update(event_id)
        if event is None or event.status != "Open":
            raise EventUnavailableError
        if self.repository.is_registered(alumnus_id, event_id):
            raise AlreadyRegisteredError
        if self.repository.registration_count(event_id) >= event.capacity:
            raise EventUnavailableError

        return self.repository.create_registration(
            EventRegistration(
                alumnus_id=alumnus_id,
                event_id=event_id,
                status="Pending",
            )
        )

    def list_registrations(self, user_id: int) -> list[AlumniRegistration]:
        alumnus_id = self.repository.get_alumnus_id(user_id)
        if alumnus_id is None:
            raise ProfileRequiredError
        return [
            AlumniRegistration(registration=registration, event=event)
            for registration, event in self.repository.list_registrations_for_alumnus(
                alumnus_id
            )
        ]
