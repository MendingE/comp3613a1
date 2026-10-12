from sqlmodel import Field, SQLModel


class Alumnus(SQLModel, table=True):
    alumni_id: int | None = Field(default=None, primary_key=True)

    # STUDENT SNIPPET START: add the FastStarter account link for this profile.
    user_id: int = Field(foreign_key="user.id", unique=True, index=True)
    # STUDENT SNIPPET END

    first_name: str = ""
    last_name: str = ""
    email: str = ""
    graduation_year: int | None = None
    degree: str = ""
    current_occupation: str = ""
    company: str = ""
    bio: str = ""
    profile_photo: str | None = None
