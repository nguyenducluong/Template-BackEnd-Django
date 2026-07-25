"""
Lightweight replacement for ``django.contrib.auth.models.AnonymousUser``.

Because we no longer depend on ``django.contrib.auth``, we provide our own
anonymous-user stand-in so that request / scope objects have a consistent
interface even when the caller is not authenticated.
"""


class AnonymousUser:
    """Minimal anonymous-user object compatible with our views & consumers."""

    is_authenticated = False
    is_anonymous = True
    pk = None
    id = None
    gen_id = None
    knox_id = None
    full_name = ""
    status = None

    def __str__(self) -> str:
        return "AnonymousUser"

    def __eq__(self, other) -> bool:
        return isinstance(other, AnonymousUser)

    def __hash__(self) -> int:
        return hash("AnonymousUser")
