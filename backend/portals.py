"""Les deux portails hors communauté : le clinicien et l'équipe (admin).

Le clinicien voit les patients qui l'ont désigné à l'inscription (même e-mail), leur bien-être lu
par les réseaux et leur activité, mais jamais le contenu de leurs échanges. Il y laisse ses notes.
L'admin voit toute la communauté, les échanges et les messages envoyés à l'équipe.
"""

from backend import schemas
from backend.errors import ApiError
from backend.store import Store, User
from backend.views import app_user


def clinician_home(store: Store, clinician: User) -> schemas.ClinicianHome:
    return schemas.ClinicianHome(
        user=app_user(clinician),
        patients=[
            _followed(store, patient) for patient in store.patients_of_clinician(clinician.email)
        ],
    )


def save_notes(
    store: Store, clinician: User, patient_id: str, notes: schemas.ClinicianNotes
) -> schemas.ClinicianHome:
    followed = {patient.id for patient in store.patients_of_clinician(clinician.email)}
    if patient_id not in followed:
        raise ApiError(404, "patient_not_found", "This patient is not followed by you.")
    store.save_note(
        patient_id, clinician.id, notes.mood.strip(), notes.proud.strip(), notes.loves.strip()
    )
    return clinician_home(store, clinician)


def _followed(store: Store, patient: User) -> schemas.ClinicianPatient:
    requests = store.requests_of("patient", patient.id)
    handled = sorted(
        (item for item in requests if item.answered_at is not None),
        key=lambda item: item.answered_at or 0.0,
    )
    moments = [
        moment
        for item in requests
        for moment in (item.delivered_at, item.answered_at)
        if moment is not None
    ]
    trend: list[schemas.TrendPoint] = []
    if handled and handled[0].theta_before is not None:  # le point de départ, avant la 1re demande
        start = handled[0].delivered_at or patient.created_at
        trend.append(schemas.TrendPoint(at=start, wellbeing=_unit(handled[0].theta_before)))
    trend += [
        schemas.TrendPoint(at=item.answered_at or 0.0, wellbeing=_unit(item.theta_after))
        for item in handled
        if item.theta_after is not None
    ]
    note = store.note(patient.id)
    return schemas.ClinicianPatient(
        id=patient.id,
        first_name=patient.first_name,
        last_name=patient.last_name,
        city=patient.city,
        birth_date=patient.birth_date,
        avatar_url=patient.avatar_url,
        interests=patient.interests,
        bio=patient.bio,
        joined_at=patient.created_at,
        wellbeing=_unit(patient.theta),
        answered=sum(item.status == "answered" for item in requests),
        declined=sum(item.status == "declined" for item in requests),
        waiting=sum(item.status == "delivered" for item in requests),
        last_activity=max(moments) if moments else None,
        trend=trend,
        notes=schemas.ClinicianNotesView(
            mood=note.mood, proud=note.proud, loves=note.loves, updated_at=note.updated_at
        )
        if note
        else None,
    )


def _unit(value: float | None) -> float:
    return min(1.0, max(0.0, value or 0.0))


# --- Admin ----------------------------------------------------------------------------------


def admin_home(store: Store, admin: User) -> schemas.AdminHome:
    users = store.users()
    names = {user.id: user.full_name for user in users}
    requests = store.all_requests()
    activity: dict[str, int] = {}
    for request in requests:
        activity[request.helper_id] = activity.get(request.helper_id, 0) + 1
        activity[request.patient_id] = activity.get(request.patient_id, 0) + 1

    exchanges = [
        schemas.AdminExchange(
            id=request.id,
            kind="request",
            from_name=names.get(request.helper_id, "Someone"),
            to_name=names.get(request.patient_id),
            text=request.text,
            status=request.status,  # type: ignore[arg-type]
            reply=request.reply,
            created_at=request.created_at,
        )
        for request in requests
    ] + [
        schemas.AdminExchange(
            id=need.id,
            kind="need",
            from_name=names.get(need.patient_id, "Someone"),
            to_name=names.get(need.helper_id) if need.helper_id else None,
            text=need.text,
            status="taken" if need.helper_id else "open",
            reply=None,
            created_at=need.created_at,
        )
        for need in store.needs()
    ]
    exchanges.sort(key=lambda item: item.created_at, reverse=True)

    return schemas.AdminHome(
        user=app_user(admin),
        members=[
            schemas.AdminMember(
                id=user.id,
                role=user.role,  # type: ignore[arg-type]
                name=user.full_name,
                email=user.email,
                city=user.city,
                avatar_url=user.avatar_url,
                interests=user.interests,
                created_at=user.created_at,
                activity=activity.get(user.id, 0),
            )
            for user in users
        ],
        exchanges=exchanges,
        feedback=[
            schemas.AdminFeedback(
                id=item.id,
                sender_name=item.sender_name,
                sender_role=item.sender_role,  # type: ignore[arg-type]
                category=item.category,  # type: ignore[arg-type]
                message=item.message,
                created_at=item.created_at,
                resolved=item.resolved,
            )
            for item in store.feedback()
        ],
    )


def resolve_feedback(
    store: Store, admin: User, feedback_id: str, resolved: bool
) -> schemas.AdminHome:
    if not store.set_feedback_resolved(feedback_id, resolved):
        raise ApiError(404, "feedback_not_found", "This message does not exist.")
    return admin_home(store, admin)


def send_feedback(store: Store, user: User | None, body: schemas.FeedbackRequest) -> None:
    store.add_feedback(
        user_id=user.id if user else None,
        sender_name=user.full_name if user else "Visitor",
        sender_role=user.role if user else "visitor",
        category=body.category,
        message=body.message.strip(),
    )
