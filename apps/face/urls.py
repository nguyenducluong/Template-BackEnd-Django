from django.urls import path
from .views import FaceRegisterView, FaceSearchView, FaceVerifyView

app_name = "face"

urlpatterns = [
    path("register/", FaceRegisterView.as_view(), name="register"),
    path("search/", FaceSearchView.as_view(), name="search"),
    path("verify/", FaceVerifyView.as_view(), name="verify"),
]