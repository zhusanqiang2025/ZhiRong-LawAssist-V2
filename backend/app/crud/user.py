# backend/app/crud/user.py (最终决定版)
from sqlalchemy.orm import Session
# <<< 核心修正点: 直接、精确地导入所需的模型和Schema >>>
from app.models.user import User
from app.schemas import UserCreate, UserUpdate
from app.core.security import get_password_hash, verify_password
from app.crud.base import CRUDBase

class CRUDUser(CRUDBase[User, UserCreate, UserUpdate]):
    def get_by_email(self, db: Session, *, email: str) -> User | None:
        return db.query(User).filter(User.email == email).first()

    def get_by_phone(self, db: Session, *, phone: str) -> User | None:
        """根据手机号查询用户"""
        return db.query(User).filter(User.phone == phone).first()

    def get_by_email_or_phone(self, db: Session, *, email: str = None, phone: str = None) -> User | None:
        """根据邮箱或手机号查询用户"""
        query = db.query(User)
        if email:
            query = query.filter(User.email == email)
        if phone:
            query = query.filter(User.phone == phone)
        return query.first()

    def create(self, db: Session, *, obj_in: UserCreate) -> User:
        db_obj = User(
            email=obj_in.email,
            phone=obj_in.phone,
            hashed_password=get_password_hash(obj_in.password),
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def authenticate(
        self, db: Session, *, email: str, password: str
    ) -> User | None:
        user = self.get_by_email(db, email=email)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

user = CRUDUser(User)