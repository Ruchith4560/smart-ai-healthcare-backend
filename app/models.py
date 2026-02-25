from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True)
    password = Column(String, nullable=False)
    role = Column(String, default="patient")
    specialization = Column(String, nullable=True)


class SymptomHistory(Base):
    __tablename__ = "symptom_history"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("users.id"))
    symptoms = Column(String)
    predicted_specialization = Column(String)
    diagnosis = Column(String, nullable=True)
    prescription = Column(String, nullable=True)

    patient = relationship("User")
from sqlalchemy import DateTime
from datetime import datetime
from sqlalchemy import Text

class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("users.id"))
    doctor_id = Column(Integer, ForeignKey("users.id"))
    appointment_time = Column(DateTime)
    status = Column(String, default="booked")
    doctor_notes = Column(Text, nullable=True)

    patient = relationship("User", foreign_keys=[patient_id])
    doctor = relationship("User", foreign_keys=[doctor_id])

   
class DoctorAvailability(Base):
    __tablename__ = "doctor_availability"

    id = Column(Integer, primary_key=True, index=True)
    doctor_id = Column(Integer, ForeignKey("users.id"))
    available_time = Column(DateTime, nullable=False)
    is_booked = Column(String, default="no")

    doctor = relationship("User")


class ChatHistory(Base):
    __tablename__ = "chat_history"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("users.id"))
    message = Column(String)
    bot_reply = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    patient = relationship("User")