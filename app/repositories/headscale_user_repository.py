from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.headscale_user import HeadscaleUser


class HeadscaleUserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, user_id: str) -> HeadscaleUser | None:
        return self.db.get(HeadscaleUser, user_id)

    def get_by_name(self, name: str) -> HeadscaleUser | None:
        return self.db.scalar(
            select(HeadscaleUser).where(HeadscaleUser.name == name)
        )

    def get_by_environment(self, environment_id: str) -> HeadscaleUser | None:
        return self.db.scalar(
            select(HeadscaleUser).where(HeadscaleUser.environment_id == environment_id)
        )

    def get_by_headscale_id(self, headscale_user_id: str) -> HeadscaleUser | None:
        return self.db.scalar(
            select(HeadscaleUser).where(HeadscaleUser.headscale_user_id == headscale_user_id)
        )

    def create(self, *, environment_id: str, headscale_user_id: str, name: str) -> HeadscaleUser:
        db_user = HeadscaleUser(
            environment_id=environment_id,
            headscale_user_id=headscale_user_id,
            name=name
        )
        self.db.add(db_user)
        self.db.flush()
        return db_user

    def update(self, db_user: HeadscaleUser, *, name: str) -> HeadscaleUser:
        db_user.name = name
        self.db.flush()
        return db_user

    def delete(self, db_user: HeadscaleUser) -> None:
        self.db.delete(db_user)
        self.db.flush()
