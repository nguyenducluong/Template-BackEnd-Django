from django.db import models
from django.utils.translation import gettext as _

from rest_framework import viewsets
from rest_framework.decorators import action

from libs.responses import EnvelopeMixin, success_response

from .models import GroupHeader, PagesHeader, SystemHeader
from .serializers import GroupHeaderSerializer, PagesHeaderSerializer, SystemHeaderSerializer


class HeaderStructureViewSet(viewsets.ReadOnlyModelViewSet):
    """
    3-level header structure:
      GroupHeader -> PagesHeader -> SystemHeader

    GET /api/v1/info/headers/structure/  returns the full nested tree.
    """

    @action(detail=False, methods=["get"], url_path="structure")
    def structure(self, request):
        # prefetch_related avoids N+1 queries: 1 query for groups + 1 for all
        # pages + 1 for all system headers, instead of 1 per group/page.
        groups = (
            GroupHeader.objects.filter(is_use=True)
            .prefetch_related(
                models.Prefetch(
                    "pages",
                    queryset=PagesHeader.objects.filter(is_use=True).order_by("sort", "id").prefetch_related(
                        models.Prefetch(
                            "system_headers",
                            queryset=SystemHeader.objects.filter(is_use=True).order_by("sort", "id"),
                        )
                    ),
                )
            )
            .order_by("sort", "id")
        )
        data = []
        for group in groups:
            pages = group.pages.filter(is_use=True).order_by("sort", "id")
            page_list = []
            for page in pages:
                headers = page.system_headers.filter(is_use=True).order_by("sort", "id")
                page_list.append({
                    "id": page.id,
                    "page_vi": page.page_vi,
                    "page_en": page.page_en,
                    "page_kr": page.page_kr,
                    "is_use": page.is_use,
                    "headers": SystemHeaderSerializer(headers, many=True).data,
                })
            data.append({
                "id": group.id,
                "group_vi": group.group_vi,
                "group_en": group.group_en,
                "group_kr": group.group_kr,
                "is_use": group.is_use,
                "pages": page_list,
            })
        return success_response(data=data, message=_("Header structure"))


class GroupHeaderViewSet(EnvelopeMixin, viewsets.ReadOnlyModelViewSet):
    queryset = GroupHeader.objects.all()
    serializer_class = GroupHeaderSerializer


class PagesHeaderViewSet(EnvelopeMixin, viewsets.ReadOnlyModelViewSet):
    queryset = PagesHeader.objects.all()
    serializer_class = PagesHeaderSerializer


class SystemHeaderViewSet(EnvelopeMixin, viewsets.ReadOnlyModelViewSet):
    queryset = SystemHeader.objects.select_related("page_header").all()
    serializer_class = SystemHeaderSerializer
