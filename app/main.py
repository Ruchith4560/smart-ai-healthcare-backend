from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from .database import engine, get_db
from .models import (
    Base,
    ChatHistory,
    User,
    Appointment,
    DoctorAvailability,
    SymptomHistory,
)
from .schemas import (
    UserCreate,
    UserLogin,
    AppointmentCreate,
    AvailabilityCreate,
    DiagnosisUpdate,
)
from .auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    require_role,
)
from .ai_engine import suggest_specialization


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

    return history


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

    return history


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


@app.post("/doctor/availability")
def add_availability(
    data: AvailabilityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("doctor"))
):
    slot = DoctorAvailability(
    doctor_id=current_user.id,
    available_time=data.available_time
)
    db.add(slot)
    db.commit()
    db.refresh(slot)

    return {"message": "Availability slot added"}


@app.get("/doctor/{doctor_id}/availability")
def get_doctor_availability(
    doctor_id: int,
    db: Session = Depends(get_db)
):
    slots = db.query(DoctorAvailability).filter(
        DoctorAvailability.doctor_id == doctor_id,
        DoctorAvailability.is_booked == "no"
    ).all()

    return [
        {
            "slot_id": slot.id,
            "available_time": slot.available_time
        }
        for slot in slots
    ]




@app.post("/appointments/book")
def book_appointment(
    data: AppointmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("patient"))
):
    slot = db.query(DoctorAvailability).filter(
        DoctorAvailability.id == data.slot_id,
        DoctorAvailability.is_booked == "no"
    ).first()

    if not slot:
        raise HTTPException(status_code=400, detail="Slot not available")

    appointment = Appointment(
        patient_id=current_user.id,
        doctor_id=slot.doctor_id,
        appointment_time=slot.available_time,
        status="booked"
    )

    slot.is_booked = "yes"

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
    return db.query(Appointment).filter(
        Appointment.patient_id == current_user.id
    ).all()


@app.get("/appointments/doctor")
def get_doctor_appointments(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("doctor"))
):
    return db.query(Appointment).filter(
        Appointment.doctor_id == current_user.id
    ).all()


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

    return {"message": "Appointment cancelled successfully"}
from .schemas import AppointmentComplete


@app.put("/appointments/complete/{appointment_id}")
def complete_appointment(
    appointment_id: int,
    data: AppointmentComplete,
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
    appointment.doctor_notes = data.notes

    db.commit()
    db.refresh(appointment)

    return {"message": "Appointment marked as completed"}
from .schemas import ChatRequest
from .ai_engine import medical_chatbot_response
@app.post("/ai/chat")
def ai_chat(
    data: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("patient"))
):
    reply, specialization = medical_chatbot_response(data.message)

    # Save chat history
    chat = ChatHistory(
        patient_id=current_user.id,
        message=data.message,
        bot_reply=reply
    )

    db.add(chat)
    db.commit()
    db.refresh(chat)

    doctors = []
    if specialization:
        doctors = db.query(User).filter(
            User.role == "doctor",
            User.specialization.ilike(specialization)
        ).all()

    return {
        "user_message": data.message,
        "bot_reply": reply,
        "recommended_specialization": specialization,
        "available_doctors": [
            {
                "id": doc.id,
                "name": doc.name,
                "specialization": doc.specialization
            }
            for doc in doctors
        ]
    }
@app.get("/ai/chat/history")
def get_chat_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("patient"))
):
    chats = db.query(ChatHistory).filter(
        ChatHistory.patient_id == current_user.id
    ).all()

    return [
        {
            "message": chat.message,
            "reply": chat.bot_reply,
            "time": chat.created_at
        }
        for chat in chats
    ]