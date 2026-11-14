"""Comment une personne enregistrée se montre : à elle-même, et aux autres membres."""

from backend import schemas
from backend.store import User


def app_user(user: User) -> schemas.AppUser:
    return schemas.AppUser(
        id=user.id,
        role=user.role,  # type: ignore[arg-type]
        email=user.email,
        name=user.name,
        first_name=user.first_name,
        last_name=user.last_name,
        city=user.city,
        birth_date=user.birth_date,
        bio=user.bio,
        avatar_url=user.avatar_url,
        passion_photos=user.passion_photos,
        clinician_email=user.clinician_email,
        allow_profile_view=user.allow_profile_view,
        interests=user.interests,
        created_at=user.created_at,
    )


def public_profile(user: User) -> schemas.PublicProfile:
    """Profil privé : le prénom, le rôle et l'avatar, rien de plus."""
    visible = user.allow_profile_view
    return schemas.PublicProfile(
        id=user.id,
        role=user.role,  # type: ignore[arg-type]
        name=user.name,
        last_name=user.last_name if visible else "",
        city=user.city if visible else "",
        avatar_url=user.avatar_url,
        bio=user.bio if visible else "",
        interests=user.interests if visible else [],
        passion_photos=user.passion_photos if visible else [],
        visible=visible,
    )
