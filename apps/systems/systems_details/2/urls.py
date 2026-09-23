from django.urls import path

import importlib

# Package "2" bắt đầu bằng chữ số → không dùng được câu lệnh import thường
views = importlib.import_module("apps.systems.systems_details.2.views")

urlpatterns = [
	path("", views.Header2DetailsView.as_view(), name="system-details-2"),
]
