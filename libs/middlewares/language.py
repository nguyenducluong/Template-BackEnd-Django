"""
Language middleware for multi-language support.
Reads language from 'Accept-Language' header and activates it.
Supported languages: vi (Vietnamese), en (English), kr (Korean).

Properly parses full Accept-Language headers with q-values and language
subtags, e.g. "en-US,vi;q=0.9,en;q=0.8" -> picks the highest-priority
supported variant (here `vi` from the client's preference order).
"""
from django.conf import settings
from django.utils import translation
from django.utils.translation.trans_real import parse_accept_lang_header


class LanguageMiddleware:
    """
    Middleware to set the active language based on the 'Accept-Language' header.

    - Parses q-values and handles subtag matching (vi-VN -> vi).
    - Falls back through the client's preference list to the first supported
      language, then to the server default if none match.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.supported = {code for code, _ in settings.LANGUAGES}
        # Map standard ISO 639-1 codes to the app's internal language codes.
        # The app uses "kr" (to match _kr DB columns) while browsers send "ko".
        self.language_aliases = {}
        for code, _ in settings.LANGUAGES:
            self.language_aliases.setdefault(code, code)
        # ISO -> internal overrides
        self.language_aliases["ko"] = "kr"
        self.language_aliases["ko-kr"] = "kr"

    def _best_lang(self, header):
        """Return the best supported language code for the header, or None."""
        for raw_code, _ in parse_accept_lang_header(header):
            normalized = raw_code.lower()
            # Try alias first (ko -> kr), then the code itself and its subtag.
            candidates = [self.language_aliases.get(normalized), normalized, normalized.split("-")[0]]
            for candidate in candidates:
                if not candidate:
                    continue
                candidate_lower = candidate.lower()
                # Match internal code directly, or normalize if alias maps to it.
                internal = self.language_aliases.get(candidate_lower, candidate_lower)
                if internal in self.supported:
                    return internal
        return None

    def __call__(self, request):
        header = request.headers.get("Accept-Language", "")
        lang = self._best_lang(header) if header else None

        if not lang:
            lang = settings.LANGUAGE_CODE

        translation.activate(lang)
        request.LANGUAGE_CODE = lang

        response = self.get_response(request)

        # Set Content-Language in response
        response["Content-Language"] = translation.get_language()

        return response