"""
Routing của app `info` — CHỈ còn 1 endpoint POST (dispatcher).

    POST /api/v1/info/dispatch   {resource, action, id, data, params}

Quy ước dự án: KHÔNG dùng PUT / PATCH / DELETE (xem ``libs/http_policy.py``).
Router cũ (``SimpleRouter``) đã bị bỏ vì:

    - Sinh ra PUT/PATCH/DELETE cho mọi viewset ⇒ trái quy ước.
    - Gây trùng ``operationId`` trong OpenAPI (``v1_info_headers_retrieve`` vs
      ``v1_info_headers_retrieve_2``) và 1 lỗi schema vì có viewset không khai
      ``serializer_class``.
    - Menu hệ thống thực tế của FE lấy từ ``GET /api/v1/systems/default/get_systems``
      nên các route list/retrieve rời rạc không còn cần thiết.
"""

from django.urls import path

from . import views

urlpatterns = [
    # POST /api/v1/info/dispatch — dispatcher duy nhất của app info
    path("dispatch", views.InfoDispatchView.as_view(), name="info-dispatch"),
]
