from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from app.schemas import DiagnosisUpdate
from .database import engine, get_db
from .models import Base, User, SymptomHistory
from .schemas import UserCreate, UserLogin
from .auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    require_role,
)
from .ai_engine import suggest_specialization
from .models import Appointment
from .schemas import AppointmentCreate

app = FastAPI()

Base.metadata.create_all(bind=engine)




@app.get("/")
def home():
    return {"message": "Smart AI Healthcare System Running 🚀"}




@app.post("/register")
def register(user: UserCreate, db: Session = Depends(get_db)):

    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_pw = hash_password(user.password)

    new_user = User(
        name=user.name,
        email=user.email,
        password=hashed_pw,
        role=user.role,
        specialization=user.specialization,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"message": "User registered successfully"}


@app.post("/login")
def login(user: UserLogin, db: Session = Depends(get_db)):

    db_user = db.query(User).filter(User.email == user.email).first()

    if not db_user:
        raise HTTPException(status_code=400, detail="Invalid email or password")

    if not verify_password(user.password, db_user.password):
        raise HTTPException(status_code=400, detail="Invalid email or password")

    access_token = create_access_token(
        data={"user_id": db_user.id, "role": db_user.role}
    )

    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/profile")
def get_profile(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "role": current_user.role,
    }




@app.get("/doctor/dashboard")
def doctor_dashboard(user: User = Depends(require_role("doctor"))):
    return {"message": f"Welcome Doctor {user.name}"}


@app.get("/patient/dashboard")
def patient_dashboard(user: User = Depends(require_role("patient"))):
    return {"message": f"Welcome Patient {user.name}"}




@app.get("/doctors")
def list_doctors(
    specialization: Optional[str] = None,
    db: Session = Depends(get_db),
):

    query = db.query(User).filter(User.role == "doctor")

    if specialization:
        query = query.filter(User.specialization.ilike(specialization))

    doctors = query.all()

    return [
        {
            "id": doctor.id,
            "name": doctor.name,
            "email": doctor.email,
            "specialization": doctor.specialization,
        }
        for doctor in doctors
    ]




class SymptomRequest(BaseModel):
    symptoms: List[str]


@app.post("/ai/suggest-doctor")
def suggest_doctor(
    data: SymptomRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("patient")),
):

    specialization = suggest_specialization(data.symptoms)

    # Save history
    history = SymptomHistory(
        patient_id=current_user.id,
        symptoms=", ".join(data.symptoms),
        predicted_specialization=specialization,
    )

    db.add(history)
    db.commit()

    doctors = db.query(User).filter(
        User.role == "doctor",
        User.specialization.ilike(specialization),
    ).all()

    return {
        "recommended_specialization": specialization,
        "available_doctors": [
            {
                "id": doctor.id,
                "name": doctor.name,
                "specialization": doctor.specialization,
            }
            for doctor in doctors
        ],
    }
@app.get("/patient/history")
def get_patient_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("patient"))
):
    history = db.query(SymptomHistory).filter(
        SymptomHistory.patient_id == current_user.id
    ).all()

    return [
        {
            "id": record.id,
            "symptoms": record.symptoms,
            "predicted_specialization": record.predicted_specialization
        }
        for record in history
    ]
@app.get("/doctor/patient-history/{patient_id}")
def get_patient_history_for_doctor(
    patient_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("doctor"))
):
    patient = db.query(User).filter(
        User.id == patient_id,
        User.role == "patient"
    ).first()

    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    history = db.query(SymptomHistory).filter(
        SymptomHistory.patient_id == patient_id
    ).all()

    return {
        "patient_name": patient.name,
        "history": [
            {
                "id": record.id,
                "symptoms": record.symptoms,
                "predicted_specialization": record.predicted_specialization
            }
            for record in history
        ]
    }
@app.put("/doctor/diagnose/{history_id}")
def add_diagnosis(
    history_id: int,
    data: DiagnosisUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("doctor"))
):
    record = db.query(SymptomHistory).filter(
        SymptomHistory.id == history_id
    ).first()

    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    record.diagnosis = data.diagnosis
    record.prescription = data.prescription

    db.commit()
    db.refresh(record)

    return {"message": "Diagnosis added successfully"}
@app.post("/appointments/book")
def book_appointment(
    data: AppointmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("patient"))
):
    doctor = db.query(User).filter(
        User.id == data.doctor_id,
        User.role == "doctor"
    ).first()

    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")

    appointment = Appointment(
        patient_id=current_user.id,
        doctor_id=data.doctor_id,
        appointment_time=data.appointment_time
    )

    db.add(appointment)
    db.commit()
    db.refresh(appointment)

    return {
        "message": "Appointment booked successfully",
        "appointment_id": appointment.id
    }
@app.get("/appointments/my")
def get_my_appointments(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("patient"))
):
    appointments = db.query(Appointment).filter(
        Appointment.patient_id == current_user.id
    ).all()

    return [
        {
            "id": appt.id,
            "doctor_id": appt.doctor_id,
            "appointment_time": appt.appointment_time,
            "status": appt.status
        }
        for appt in appointments
    ]
@app.get("/appointments/doctor")
def get_doctor_appointments(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("doctor"))
):
    appointments = db.query(Appointment).filter(
        Appointment.doctor_id == current_user.id
    ).all()

    return [
        {
            "id": appt.id,
            "patient_id": appt.patient_id,
            "appointment_time": appt.appointment_time,
            "status": appt.status
        }
        for appt in appointments
    ]
@app.put("/appointments/cancel/{appointment_id}")
def cancel_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("patient"))
):
    appointment = db.query(Appointment).filter(
        Appointment.id == appointment_id,
        Appointment.patient_id == current_user.id
    ).first()

    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if appointment.status != "booked":
        raise HTTPException(status_code=400, detail="Cannot cancel this appointment")

    appointment.status = "cancelled"

    db.commit()
    db.refresh(appointment)

    return {"message": "Appointment cancelled successfully"}
@app.put("/appointments/complete/{appointment_id}")
def complete_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("doctor"))
):
    appointment = db.query(Appointment).filter(
        Appointment.id == appointment_id,
        Appointment.doctor_id == current_user.id
    ).first()

    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if appointment.status != "booked":
        raise HTTPException(status_code=400, detail="Cannot complete this appointment")

    appointment.status = "completed"

    db.commit()
    db.refresh(appointment)

    return {"message": "Appointment marked as completed"}