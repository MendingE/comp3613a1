import logging

from sqlmodel import Session, select

from app.models.alumnus import Alumnus

logger = logging.getLogger(__name__)


class AlumnusRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_user_id(self, user_id: int) -> Alumnus | None:
        statement = select(Alumnus).where(Alumnus.user_id == user_id)
        return self.db.exec(statement).one_or_none()

    def save(self, profile: Alumnus) -> Alumnus:
        try:
            self.db.add(profile)
            self.db.commit()
            self.db.refresh(profile)
            return profile
        except Exception:
            logger.exception("Failed to save alumnus profile")
            self.db.rollback()
            raise
