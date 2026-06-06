from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, JSON, String
from sqlalchemy.orm import relationship

from db.database import Base


class Session(Base):
    __tablename__ = "sessions"

    # Primary key is the Telegram user ID (stored as string)
    id = Column(String, primary_key=True)
    state = Column(String)
    data = Column(JSON)  # collected conversation data
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Session id={self.id} state={self.state}>"


class Giro(Base):
    __tablename__ = "giros"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String)
    scian = Column(String)
    impacto = Column(String)        # bajo / vecinal / zonal
    formato_siapem = Column(String) # EM-03 / EM-11 / EM-08
    descripcion = Column(String)
    keywords = Column(JSON)

    def __repr__(self):
        return f"<Giro nombre={self.nombre} impacto={self.impacto}>"


class Interaction(Base):
    __tablename__ = "interactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String)
    action = Column(String)
    giro = Column(String, nullable=True)
    zona = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Interaction user_id={self.user_id} action={self.action}>"
