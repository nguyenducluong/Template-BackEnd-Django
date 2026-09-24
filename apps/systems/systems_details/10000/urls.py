from django.urls import path

import importlib

# Package "10000" bắt đầu bằng chữ số → không dùng được câu lệnh import thường.
# LƯU Ý: urls này KHÔNG nối vào router cha (apps.systems.urls) — header mẫu
# không bao giờ lọt production. Chỉ dùng để test import trực tiếp.
views = importlib.import_module('apps.systems.systems_details.10000.views')

urlpatterns = [
	path('', views.Header10000DetailsView.as_view(), name='system-details-10000'),
]
