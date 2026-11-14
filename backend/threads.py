"""Les fils de discussion de la vraie app, tels que chacun des deux les lit.

Un fil naît d'une demande : un aidant écrit à un patient, choisi par la boucle. La demande, la
réponse et le merci restent dans la table des demandes, parce que la boucle en apprend ; les
messages qui suivent sont dans la table `messages`.

Ce que chacun voit :
- l'aidant voit toutes ses demandes, mais jamais si l'une est retenue, transmise ou déclinée :
  pour lui, elle est « en route » tant qu'il n'a pas de réponse ;
- le patient ne voit que les demandes qui lui sont transmises et celles auxquelles il a répondu.
"""

from backend import schemas
from backend.community import Community
from backend.errors import ApiError
from backend.store import StoredRequest, User
from backend.views import public_profile


class Threads:
    def __init__(self, community: Community) -> None:
        self.community = community
        self.store = community.store

    # --- Lecture ---------------------------------------------------------------------------

    def for_user(self, user: User) -> schemas.ThreadsResponse:
        threads = [
            thread
            for request in self.store.requests_of(user.role, user.id)
            if (thread := self._request_thread(user, request)) is not None
        ]
        threads.sort(key=lambda thread: thread.updated_at, reverse=True)
        return schemas.ThreadsResponse(threads=threads)

    def _request_thread(self, user: User, request: StoredRequest) -> schemas.Thread | None:
        as_helper = user.role == "helper"
        if not as_helper and request.status not in ("delivered", "answered"):
            return None  # retenue ou déclinée : le patient ne la voit pas
        if request.status == "answered":
            status = "answered"
        else:
            status = "on_its_way" if as_helper else "to_answer"
        helper, patient = self.store.user(request.helper_id), self.store.user(request.patient_id)
        peer = patient if as_helper else helper
        names = {
            request.helper_id: helper.name if helper else "Someone",
            request.patient_id: patient.name if patient else "Someone",
        }
        sent_at = request.created_at if as_helper else (request.delivered_at or request.created_at)
        messages = [
            self._message(
                user, f"{request.id}-q", request.helper_id, names, "request", request.text, sent_at
            ),
        ]
        if request.reply is not None:
            answered_at = request.answered_at or sent_at
            messages.append(
                self._message(
                    user,
                    f"{request.id}-r",
                    request.patient_id,
                    names,
                    "reply",
                    request.reply,
                    answered_at,
                )
            )
            if request.thanks:
                messages.append(
                    self._message(
                        user,
                        f"{request.id}-t",
                        request.helper_id,
                        names,
                        "thanks",
                        request.thanks,
                        request.thanked_at or answered_at,
                    )
                )
        messages += self._extra(user, request.id, names)
        messages.sort(key=lambda message: message.created_at)
        return schemas.Thread(
            id=request.id,
            status=status,
            peer=public_profile(peer) if peer else None,
            messages=messages,
            updated_at=messages[-1].created_at,
            can_write=status in ("answered", "to_answer"),
            thanked=bool(request.thanks),
        )

    def _extra(
        self, user: User, thread_id: str, names: dict[str, str]
    ) -> list[schemas.ThreadMessage]:
        return [
            self._message(
                user,
                message.id,
                message.sender_id,
                names,
                "message",
                message.text,
                message.created_at,
                message.attachments,
            )
            for message in self.store.messages_of(thread_id)
        ]

    @staticmethod
    def _message(
        user: User,
        message_id: str,
        sender_id: str,
        names: dict[str, str],
        kind: schemas.MessageKind,
        text: str,
        created_at: float,
        attachments: list[dict] | None = None,
    ) -> schemas.ThreadMessage:
        return schemas.ThreadMessage(
            id=message_id,
            mine=sender_id == user.id,
            sender_name=names.get(sender_id, "Someone"),
            kind=kind,
            text=text,
            attachments=[schemas.Attachment(**item) for item in attachments or []],
            created_at=created_at,
        )

    # --- Écriture --------------------------------------------------------------------------

    def post(
        self, user: User, thread_id: str, body: schemas.MessageRequest
    ) -> schemas.ThreadsResponse:
        text = body.text.strip()
        attachments = [item.model_dump() for item in body.attachments]
        if not text and not attachments:
            raise ApiError(422, "empty_message", "Write something first.")

        request = self.store.request(thread_id)
        if request is None or user.id not in (request.helper_id, request.patient_id):
            raise ApiError(404, "thread_not_found", "This conversation does not exist.")
        self._post_on_request(user, request, text, attachments, body.typing)
        return self.for_user(user)

    def _post_on_request(
        self,
        user: User,
        request: StoredRequest,
        text: str,
        attachments: list[dict],
        typing: schemas.TypingSignals | None,
    ) -> None:
        if user.id == request.patient_id and request.status == "delivered":
            if not text:
                raise ApiError(422, "empty_message", "Write a few words to answer.")
            self.community.reply(user, request.id, text, typing)  # étapes 9 à 12
        elif user.id == request.helper_id and request.status == "answered" and not request.thanks:
            if text:
                self.community.thank(user, request.id, text)
            else:
                text = ""  # une pièce jointe seule ne remplace pas le merci
        elif request.status != "answered":
            raise ApiError(409, "not_yet", "Wait for the answer before writing again.")
        elif text:
            self.store.add_message(request.id, user.id, text, attachments)
            return
        if attachments:
            self.store.add_message(request.id, user.id, "", attachments)

    def decline(self, patient: User, thread_id: str) -> schemas.ThreadsResponse:
        self.community.decline(patient, thread_id)
        return self.for_user(patient)
