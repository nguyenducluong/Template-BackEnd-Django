from django.urls import path

import importlib

# Package "1" bắt đầu bằng chữ số → không dùng được câu lệnh import thường
views = importlib.import_module("apps.systems.systems_details.1.views")

urlpatterns = [
	path("", views.Header1DetailsView.as_view(), name="system-details-1"),
]
