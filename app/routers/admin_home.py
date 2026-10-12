from fastapi import Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session

from app.dependencies.auth import AdminDep, is_admin_dep
from app.dependencies.session import SessionDep
from app.repositories.event import EventRepository, EventRepositoryError
from app.services.admin_events_service import (
    AdminEventsService,
    AdministratorNotFoundError,
    EventDetailsUpdateConflictError,
    EventNotFoundError,
    EventOwnershipError,
    EventStatusUpdateConflictError,
    InvalidEventDetailsError,
    InvalidEventStatusError,
)
from app.utilities.flash import flash
from . import router, templates


def _admin_events_service(db: Session) -> AdminEventsService:
    return AdminEventsService(EventRepository(db))


@router.get(
    "/admin",
    response_class=HTMLResponse,
    name="admin_home_view",
    dependencies=[Depends(is_admin_dep)],
)
async def admin_home_view():
    return RedirectResponse(url="/admin/events", status_code=303)


@router.get("/admin/events", response_class=HTMLResponse, name="admin_events_view")
async def admin_events_view(
    request: Request,
    user: AdminDep,
    db: SessionDep,
    query: str = "",
):
    service = _admin_events_service(db)
    admin_error = None
    events = []
    editing_event = None

    try:
        events = service.list_events(str(user.email), query=query)
        edit_id = request.query_params.get("edit_id")
        if edit_id:
            try:
                edit_event_id = int(edit_id)
            except ValueError:
                flash(request, "The selected event is invalid.", "danger")
                return RedirectResponse(url="/admin/events", status_code=303)

            editing_event = next(
                (event for event in events if event.event_id == edit_event_id),
                None,
            )
            if editing_event is None:
                flash(
                    request,
                    "That event was not found in the events you manage.",
                    "danger",
                )
                return RedirectResponse(url="/admin/events", status_code=303)
    except AdministratorNotFoundError:
        admin_error = (
            "Your administrator record is missing. Contact the application "
            "administrator before managing events."
        )

    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={
            "user": user,
            "events": events,
            "query": query,
            "editing_event": editing_event,
            "show_create_form": request.query_params.get("create") == "1",
            "admin_error": admin_error,
        },
    )


@router.post("/admin/events", name="admin_event_create_action")
async def admin_event_create_action(
    request: Request,
    user: AdminDep,
    db: SessionDep,
    title: str = Form(...),
    description: str = Form(default=""),
    event_date: str = Form(...),
    event_time: str = Form(...),
    location: str = Form(...),
    capacity: str = Form(...),
):
    try:
        _admin_events_service(db).create_event(
            str(user.email),
            title=title,
            description=description,
            date_value=event_date,
            time_value=event_time,
            location=location,
            capacity_value=capacity,
        )
    except InvalidEventDetailsError as error:
        flash(request, str(error), "danger")
        return RedirectResponse(url="/admin/events?create=1", status_code=303)
    except AdministratorNotFoundError:
        flash(request, "Your administrator record could not be found.", "danger")
        return RedirectResponse(url="/admin/events?create=1", status_code=303)
    except EventRepositoryError:
        flash(request, "The event could not be saved. Please try again.", "danger")
        return RedirectResponse(url="/admin/events?create=1", status_code=303)

    flash(request, "Event created successfully.")
    return RedirectResponse(url="/admin/events", status_code=303)


@router.post(
    "/admin/events/{event_id}/edit", name="admin_event_update_action"
)
async def admin_event_update_action(
    request: Request,
    event_id: int,
    user: AdminDep,
    db: SessionDep,
    title: str = Form(...),
    description: str = Form(default=""),
    event_date: str = Form(...),
    event_time: str = Form(...),
    location: str = Form(...),
    capacity: str = Form(...),
):
    try:
        _admin_events_service(db).update_event_details(
            event_id,
            str(user.email),
            title=title,
            description=description,
            date_value=event_date,
            time_value=event_time,
            location=location,
            capacity_value=capacity,
        )
    except InvalidEventDetailsError as error:
        flash(request, str(error), "danger")
        return RedirectResponse(
            url=f"/admin/events?edit_id={event_id}", status_code=303
        )
    except AdministratorNotFoundError:
        flash(request, "Your administrator record could not be found.", "danger")
        return RedirectResponse(url="/admin/events", status_code=303)
    except EventNotFoundError:
        flash(request, "That event no longer exists.", "danger")
        return RedirectResponse(url="/admin/events", status_code=303)
    except EventOwnershipError:
        flash(request, "You can only edit events that you manage.", "danger")
        return RedirectResponse(url="/admin/events", status_code=303)
    except EventDetailsUpdateConflictError:
        flash(request, "The event changed while you were editing it.", "danger")
        return RedirectResponse(url="/admin/events", status_code=303)
    except EventRepositoryError:
        flash(request, "The event changes could not be saved. Please try again.", "danger")
        return RedirectResponse(
            url=f"/admin/events?edit_id={event_id}", status_code=303
        )

    flash(request, "Event details updated successfully.")
    return RedirectResponse(url="/admin/events", status_code=303)


@router.post("/admin/events/{event_id}/status", name="admin_event_status_action")
async def admin_event_status_action(
    request: Request,
    event_id: int,
    user: AdminDep,
    db: SessionDep,
    new_status: str = Form(...),
):
    try:
        _admin_events_service(db).update_event_status(
            event_id=event_id,
            admin_email=str(user.email),
            status=new_status,
        )
    except InvalidEventStatusError:
        flash(request, "Choose Open, Closed, or Cancelled.", "danger")
    except AdministratorNotFoundError:
        flash(request, "Your administrator record could not be found.", "danger")
    except EventNotFoundError:
        flash(request, "That event no longer exists.", "danger")
    except EventOwnershipError:
        flash(request, "You can only change events that you manage.", "danger")
    except EventStatusUpdateConflictError:
        flash(request, "The event changed while you were updating it.", "danger")
    except EventRepositoryError:
        flash(request, "The event status could not be saved. Please try again.", "danger")
    else:
        flash(request, "Event status updated successfully.")

    return RedirectResponse(url="/admin/events", status_code=303)
