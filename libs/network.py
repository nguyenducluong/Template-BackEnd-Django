from django.conf import settings


def get_client_ip(request) -> str:
    """Return a trustworthy client identifier for rate limiting.

    ``X-Forwarded-For`` is trivially spoofable by the client, so it is only
    honoured when the direct peer (``REMOTE_ADDR``) is a configured reverse
    proxy (``settings.TRUSTED_PROXIES``). In that case we walk the XFF chain
    right-to-left and return the first hop that is NOT itself a trusted
    proxy — the IP the trusted proxy chain actually observed. When the peer
    is not a trusted proxy we always use ``REMOTE_ADDR`` directly, so a
    client cannot reset its rate-limit quota by sending a fake header.
    """
    remote_addr = request.META.get("REMOTE_ADDR", "") or ""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    trusted = {p.strip() for p in getattr(settings, "TRUSTED_PROXIES", []) if p.strip()}

    if forwarded and remote_addr in trusted:
        for hop in reversed([h.strip() for h in forwarded.split(",")]):
            if hop and hop not in trusted:
                return hop
    return remote_addr
