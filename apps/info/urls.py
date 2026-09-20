from django.urls import include, path
from rest_framework import routers

from . import views

# trailing_slash=False: URL của router không có "/" cuối (khớp convention APPEND_SLASH=False)
router = routers.SimpleRouter(trailing_slash=False)
router.register(r"headers", views.HeaderStructureViewSet, basename="header-structure")
router.register(r"group-headers", views.GroupHeaderViewSet, basename="group-header")
router.register(r"page-headers", views.PagesHeaderViewSet, basename="page-header")
router.register(r"system-headers", views.SystemHeaderViewSet, basename="system-header")

urlpatterns = [
    path("", include(router.urls)),
]