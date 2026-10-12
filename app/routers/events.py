from fastapi import HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session

from app.dependencies.auth import AuthDep
from app.dependencies.session import SessionDep
from app.repositories.event import EventRepository
from app.services.events_service import (
    AlumniEventsService,
    AlreadyRegisteredError,
    EventUnavailableError,
    ProfileRequiredError,
)
from . import router, templates


def _events_service(db: Session) -> AlumniEventsService:
    return AlumniEventsService(EventRepository(db))


@router.get("/events", response_class=HTMLResponse, name="events_list_view")
async def events_list_view(
    request: Request,
    user: AuthDep,
    db: SessionDep,
    query: str = Query(default=""),
    event_id: int | None = Query(default=None),
):
    if user.role == "admin":
        raise HTTPException(status_code=403, detail="Event browsing is for alumni.")
    service = _events_service(db)
    events = service.list_events(query=query, user_id=user.id)
    selected_event = (
        service.get_event(event_id, user_id=user.id)
        if event_id is not None
        else None
    )
    if event_id is not None and selected_event is None:
        raise HTTPException(status_code=404, detail="Event not found.")

    return templates.TemplateResponse(
        request=request,
        name="events.html",
        context={
            "user": user,
            "events": events,
            "query": query,
            "selected_event": selected_event,
        },
    )


@router.post("/events/{event_id}/register", name="event_registration_action")
async def event_registration_action(
    event_id: int,
    user: AuthDep,
    db: SessionDep,
):
    if user.role == "admin":
        raise HTTPException(status_code=403, detail="Event registration is for alumni.")
    try:
        _events_service(db).register_for_event(event_id, user.id)
    except ProfileRequiredError:
        return RedirectResponse(
            url="/profile?error=profile_required",
            status_code=303,
        )
    except AlreadyRegisteredError:
        return RedirectResponse(
            url=f"/events?event_id={event_id}&error=already_registered",
            status_code=303,
        )
    except EventUnavailableError:
        return RedirectResponse(
            url=f"/events?event_id={event_id}&error=event_unavailable",
            status_code=303,
        )
    return RedirectResponse(url="/registrations?registered=1", status_code=303)


@router.get("/registrations", response_class=HTMLResponse, name="registrations_view")
async def registrations_view(
    request: Request,
    user: AuthDep,
    db: SessionDep,
):
    if user.role == "admin":
        raise HTTPException(status_code=403, detail="Registrations are for alumni.")
    try:
        registrations = _events_service(db).list_registrations(user.id)
    except ProfileRequiredError:
        registrations = []
    return templates.TemplateResponse(
        request=request,
        name="registrations.html",
        context={
            "user": user,
            "registrations": registrations,
            "registered": request.query_params.get("registered") == "1",
        },
    )
