"""
Custom content negotiation that safely ignores Accept-Language header.
DRF's default content negotiation can raise 406 when Accept-Language is present.
This class ensures JSON is always returned for API responses.
"""
from rest_framework.negotiation import DefaultContentNegotiation
from rest_framework.renderers import JSONRenderer
from rest_framework.exceptions import NotAcceptable


class IgnoreLanguageContentNegotiation(DefaultContentNegotiation):
    """
    Content negotiation that prevents 406 errors when Accept-Language is sent.
    Always returns JSONRenderer for API requests.
    """

    def select_renderer(self, request, renderers, format_suffix):
        try:
            return super().select_renderer(request, renderers, format_suffix)
        except NotAcceptable:
            # If DRF can't negotiate (e.g., due to Accept-Language),
            # fall back to JSONRenderer
            for renderer in renderers:
                if isinstance(renderer, JSONRenderer):
                    return (renderer, renderer.media_type)
            # If no JSONRenderer found, return the first one
            return (renderers[0], renderers[0].media_type)
