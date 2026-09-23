from django.urls import path

import importlib

# Package "3" bắt đầu bằng chữ số → không dùng được câu lệnh import thường
views = importlib.import_module("apps.systems.systems_details.3.views")

urlpatterns = [
	path("", views.Header3DetailsView.as_view(), name="system-details-3"),
]
