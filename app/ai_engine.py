def suggest_specialization(symptoms: list[str]) -> str:
    symptoms = [s.lower() for s in symptoms]

    cardiology_keywords = ["chest pain", "shortness of breath", "heart", "palpitation"]
    neurology_keywords = ["headache", "dizziness", "seizure", "migraine"]
    orthopedics_keywords = ["joint pain", "back pain", "fracture", "bone"]

    for symptom in symptoms:
        if symptom in cardiology_keywords:
            return "Cardiologist"
        if symptom in neurology_keywords:
            return "Neurologist"
        if symptom in orthopedics_keywords:
            return "Orthopedic"

    return "General Physician"
def medical_chatbot_response(message: str):
    message = message.lower()

    specialization = None
    reply = "Please provide more details."

    if "fever" in message or "infection" in message:
        specialization = "General Physician"
        reply = "It may be an infection. Stay hydrated."

    elif "heart" in message or "chest pain" in message:
        specialization = "Cardiologist"
        reply = "Chest pain can be serious. Consult a Cardiologist."

    elif "stomach" in message:
        specialization = "Gastroenterologist"
        reply = "Stomach issues may require a Gastroenterologist."

    elif "skin" in message:
        specialization = "Dermatologist"
        reply = "Skin conditions should be checked by a Dermatologist."

    return reply, specialization