from fastapi import Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.dependencies.auth import AuthDep
from app.dependencies.session import SessionDep
from app.repositories.alumnus import AlumnusRepository
from app.services.alumni_profile_service import AlumniProfileService
from . import router, templates


@router.get("/profile", response_class=HTMLResponse, name="alumni_profile_view")
async def alumni_profile_view(
    request: Request,
    user: AuthDep,
    db: SessionDep,
):
    if user.role == "admin":
        raise HTTPException(status_code=403, detail="This profile page is for alumni.")
    service = AlumniProfileService(AlumnusRepository(db))
    profile = service.get_profile(user.id)
    return templates.TemplateResponse(
        request=request,
        name="alumni_profile.html",
        context={"user": user, "profile": profile},
    )


@router.post("/profile", name="alumni_profile_save")
async def alumni_profile_save(
    user: AuthDep,
    db: SessionDep,
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    graduation_year: int = Form(...),
    degree: str = Form(...),
    current_occupation: str = Form(""),
    company: str = Form(""),
    bio: str = Form(""),
    profile_photo: str = Form(""),
):
    if user.role == "admin":
        raise HTTPException(status_code=403, detail="This profile page is for alumni.")
    # STUDENT SNIPPET START: complete the thin profile-save handler.
    service = AlumniProfileService(AlumnusRepository(db))
    service.save_profile(
        user_id=user.id,
        first_name=first_name,
        last_name=last_name,
        email=email,
        graduation_year=graduation_year,
        degree=degree,
        current_occupation=current_occupation,
        company=company,
        bio=bio,
        profile_photo=profile_photo or None,
    )
    return RedirectResponse(url="/profile?saved=1", status_code=303)
    # STUDENT SNIPPET END
