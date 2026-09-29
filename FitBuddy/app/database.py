"""Database configuration and session management for FitBuddy.

Initializes SQLite database connection using SQLAlchemy.
Provides ORM models for Users and Workout Plans, ensuring original plans
are preserved for feedback-based updates in future milestones.
"""

from datetime import datetime
import json
from typing import Dict, Any, List, Optional

from sqlalchemy import create_engine, Column, Integer, String, Float, Text, DateTime, ForeignKey, Boolean, text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

# SQLite database file stored locally in the project root
DATABASE_URL = "sqlite:///./fitbuddy.db"

# connect_args={"check_same_thread": False} is required for SQLite with multi-threaded FastAPI
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Declarative Base for ORM models
Base = declarative_base()


class User(Base):
    """User profile record model."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)
    age = Column(Integer, nullable=False)
    weight = Column(Float, nullable=False)
    fitness_goal = Column(String(50), nullable=False)
    workout_intensity = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship to workout plans
    plans = relationship("WorkoutPlan", back_populates="user", cascade="all, delete-orphan")


class WorkoutPlan(Base):
    """Generated or updated workout plan associated with a user."""
    __tablename__ = "workout_plans"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(50), ForeignKey("users.user_id"), nullable=False, index=True)
    original_plan = Column(Text, nullable=False)  # Preserved raw/JSON plan
    nutrition_tip = Column(Text, nullable=True)
    model_used = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Milestone 3 Adaptive Plan Update fields
    is_updated = Column(Boolean, default=False, nullable=False)
    parent_plan_id = Column(Integer, ForeignKey("workout_plans.id"), nullable=True, index=True)
    feedback_text = Column(Text, nullable=True)
    difficulty_preference = Column(String(50), nullable=True)

    # Relationship back to User
    user = relationship("User", back_populates="plans")
    # Relationship to parent plan (self-referential)
    parent_plan = relationship("WorkoutPlan", remote_side=[id], backref="child_updates")


def get_db():
    """FastAPI dependency that provides a database session and ensures closure."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def save_or_update_user_and_plan(
    db,
    user_data: Dict[str, Any],
    plan_data: Dict[str, Any],
    nutrition_tip: str,
    model_used: str
) -> WorkoutPlan:
    """Saves or updates user profile and associates the newly generated workout plan.

    Preserves original_plan in SQLite for future iterative updates.
    """
    user_id = str(user_data["user_id"]).strip()

    # Check if user already exists
    user = db.query(User).filter(User.user_id == user_id).first()
    if user:
        # Update user attributes
        user.name = user_data["name"]
        user.age = int(user_data["age"])
        user.weight = float(user_data["weight"])
        user.fitness_goal = user_data["fitness_goal"]
        user.workout_intensity = user_data["workout_intensity"]
    else:
        # Create new user
        user = User(
            user_id=user_id,
            name=user_data["name"],
            age=int(user_data["age"]),
            weight=float(user_data["weight"]),
            fitness_goal=user_data["fitness_goal"],
            workout_intensity=user_data["workout_intensity"]
        )
        db.add(user)

    # Commit/flush to ensure user exists
    db.flush()

    # Serialize plan structure to string for original_plan persistence
    if isinstance(plan_data, (dict, list)):
        raw_plan_text = json.dumps(plan_data, ensure_ascii=False)
    else:
        raw_plan_text = str(plan_data)

    # Create new WorkoutPlan record preserving original_plan
    workout_plan = WorkoutPlan(
        user_id=user.user_id,
        original_plan=raw_plan_text,
        nutrition_tip=nutrition_tip,
        model_used=model_used
    )
    db.add(workout_plan)
    db.commit()
    db.refresh(workout_plan)
    return workout_plan


def get_all_users(db) -> List[User]:
    """Retrieves all registered users along with their workout plans."""
    return db.query(User).order_by(User.created_at.desc()).all()


def get_plan_by_id(db, plan_id: int) -> Optional[WorkoutPlan]:
    """Retrieves a specific workout plan by ID."""
    return db.query(WorkoutPlan).filter(WorkoutPlan.id == plan_id).first()


def get_plan_updates(db, plan_id: int) -> List[WorkoutPlan]:
    """Retrieves all updated variations derived from a specific plan."""
    return db.query(WorkoutPlan).filter(WorkoutPlan.parent_plan_id == plan_id).order_by(WorkoutPlan.created_at.desc()).all()


def save_updated_plan(
    db,
    original_plan_id: int,
    user_id: str,
    updated_plan_data: Dict[str, Any],
    feedback_text: str,
    difficulty_preference: str,
    model_used: str,
    nutrition_tip: Optional[str] = None
) -> WorkoutPlan:
    """Saves an updated workout plan linked to the original plan, without mutating original plan."""
    original_plan = db.query(WorkoutPlan).filter(WorkoutPlan.id == original_plan_id).first()
    if not original_plan:
        raise ValueError(f"Original workout plan with ID {original_plan_id} not found.")

    if original_plan.user_id != user_id:
        raise PermissionError(f"User '{user_id}' does not own workout plan #{original_plan_id}.")

    if isinstance(updated_plan_data, (dict, list)):
        raw_plan_text = json.dumps(updated_plan_data, ensure_ascii=False)
    else:
        raw_plan_text = str(updated_plan_data)

    tip = nutrition_tip or original_plan.nutrition_tip

    updated_plan = WorkoutPlan(
        user_id=user_id,
        original_plan=raw_plan_text,
        nutrition_tip=tip,
        model_used=model_used,
        is_updated=True,
        parent_plan_id=original_plan.id,
        feedback_text=feedback_text,
        difficulty_preference=difficulty_preference
    )
    db.add(updated_plan)
    db.commit()
    db.refresh(updated_plan)
    return updated_plan


def ensure_schema_compatibility():
    """Ensures existing SQLite database tables contain all required Milestone 3 columns."""
    try:
        with engine.connect() as conn:
            res = conn.execute(text("PRAGMA table_info(workout_plans)")).fetchall()
            existing_cols = {row[1] for row in res}
            if existing_cols:
                if "is_updated" not in existing_cols:
                    conn.execute(text("ALTER TABLE workout_plans ADD COLUMN is_updated BOOLEAN DEFAULT 0 NOT NULL"))
                if "parent_plan_id" not in existing_cols:
                    conn.execute(text("ALTER TABLE workout_plans ADD COLUMN parent_plan_id INTEGER REFERENCES workout_plans(id)"))
                if "feedback_text" not in existing_cols:
                    conn.execute(text("ALTER TABLE workout_plans ADD COLUMN feedback_text TEXT"))
                if "difficulty_preference" not in existing_cols:
                    conn.execute(text("ALTER TABLE workout_plans ADD COLUMN difficulty_preference VARCHAR(50)"))
                conn.commit()
    except Exception as exc:
        # Tables might not be created yet during initial bootstrapping
        pass


# Run compatibility check on module load to guarantee schema matches models
ensure_schema_compatibility()
