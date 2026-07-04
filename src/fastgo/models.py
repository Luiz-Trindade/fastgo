from sqlmodel import SQLModel, Field
from datetime import datetime, timezone
from typing import Optional, Type, Dict, Any
from sqlmodel import Session, select


# Função auxiliar para obter datetime atual com timezone UTC
def utc_now():
    return datetime.now(timezone.utc)


class FastModel(SQLModel):
    """
    Modelo base do FastGo.

    Herda de SQLModel e adiciona:
    - Campos padrão: id (PK), created_at, updated_at.
    - Métodos auxiliares: save, delete, find, find_all, update.
    - Configuração automática (from_attributes = True).
    """

    # --- Campos padrão ---
    id: Optional[int] = Field(
        default=None, primary_key=True, description="Identificador único do registro"
    )

    created_at: datetime = Field(
        default_factory=utc_now,
        nullable=False,
        description="Data e hora da criação (UTC)",
    )

    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column_kwargs={"onupdate": utc_now},
        nullable=False,
        description="Data e hora da última atualização (UTC)",
    )

    # --- Configuração Pydantic ---
    class Config:
        from_attributes = True  # substitui orm_mode (depreciado)

    # --- Métodos de instância ---

    def save(self, session: Session) -> "FastModel":
        session.add(self)
        session.commit()
        session.refresh(self)
        return self

    def delete(self, session: Session) -> None:
        session.delete(self)
        session.commit()

    def update(self, session: Session, **kwargs) -> "FastModel":
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        return self.save(session)

    # --- Métodos de classe ---

    @classmethod
    def find(
        cls: Type["FastModel"], session: Session, id: int
    ) -> Optional["FastModel"]:
        return session.get(cls, id)

    @classmethod
    def find_all(
        cls: Type["FastModel"], session: Session, **filters
    ) -> list["FastModel"]:
        query = select(cls)
        for attr, value in filters.items():
            if hasattr(cls, attr):
                query = query.where(getattr(cls, attr) == value)
        return session.exec(query).all()

    @classmethod
    def find_one(
        cls: Type["FastModel"], session: Session, **filters
    ) -> Optional["FastModel"]:
        query = select(cls)
        for attr, value in filters.items():
            if hasattr(cls, attr):
                query = query.where(getattr(cls, attr) == value)
        return session.exec(query).first()

    @classmethod
    def count(cls: Type["FastModel"], session: Session, **filters) -> int:
        query = select(cls)
        for attr, value in filters.items():
            if hasattr(cls, attr):
                query = query.where(getattr(cls, attr) == value)
        return session.exec(query).count()

    # --- Métodos de criação ---

    @classmethod
    def create(cls: Type["FastModel"], session: Session, **data) -> "FastModel":
        instance = cls(**data)
        return instance.save(session)

    @classmethod
    def bulk_create(
        cls: Type["FastModel"], session: Session, items: list[Dict[str, Any]]
    ) -> list["FastModel"]:
        instances = [cls(**item) for item in items]
        session.add_all(instances)
        session.commit()
        for instance in instances:
            session.refresh(instance)
        return instances
