from app.models.alumnus import Alumnus
from app.repositories.alumnus import AlumnusRepository


class AlumniProfileService:
    def __init__(self, repository: AlumnusRepository):
        self.repository = repository

    def get_profile(self, user_id: int) -> Alumnus | None:
        return self.repository.get_by_user_id(user_id)

    def save_profile(self, user_id: int, **profile_fields: object) -> Alumnus:
        profile = self.repository.get_by_user_id(user_id)
        if profile is None:
            profile = Alumnus(user_id=user_id, **profile_fields)
        else:
            for field, value in profile_fields.items():
                setattr(profile, field, value)
        return self.repository.save(profile)
