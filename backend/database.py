from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

DATABASE_URL = "sqlite:///./racing.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Race(Base):
    __tablename__ = "races"
    id = Column(Integer, primary_key=True, index=True)
    race_id = Column(String, unique=True, index=True)
    track = Column(String)
    race_number = Column(Integer)
    race_time = Column(String)
    distance = Column(String)
    condition = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


class Horse(Base):
    __tablename__ = "horses"
    id = Column(Integer, primary_key=True, index=True)
    race_id = Column(String, index=True)
    horse_name = Column(String)
    barrier = Column(Integer)
    jockey = Column(String)
    trainer = Column(String)
    weight = Column(Float)
    tote_odds = Column(Float)
    fixed_odds = Column(Float)
    overlay_score = Column(Float)
    fair_value = Column(Float)
    is_overlay = Column(Boolean, default=False)
    updated_at = Column(DateTime, default=datetime.utcnow)


class WeatherData(Base):
    __tablename__ = "weather"
    id = Column(Integer, primary_key=True, index=True)
    track = Column(String)
    temperature = Column(Float)
    humidity = Column(Float)
    wind_speed = Column(Float)
    conditions = Column(String)
    recorded_at = Column(DateTime, default=datetime.utcnow)


class RaceResult(Base):
    __tablename__ = "race_results"
    id = Column(Integer, primary_key=True, index=True)
    race_id = Column(String, unique=True, index=True)
    track = Column(String)
    race_number = Column(Integer)
    race_date = Column(String)
    winner = Column(String)
    second = Column(String)
    third = Column(String)
    model_top_pick = Column(String, nullable=True)
    model_top_pick_won = Column(Boolean, default=False)
    model_top_pick_placed = Column(Boolean, default=False)
    entered_at = Column(DateTime, default=datetime.utcnow)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()