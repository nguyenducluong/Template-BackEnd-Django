from django.urls import path

from . import views

urlpatterns = [
    path("chat", views.AIChatView.as_view(), name="ai-chat"),
    path("faq", views.FAQListView.as_view(), name="ai-faq"),
    # Meta cho FE: cờ AI_CHAT_ENABLED + nhãn đa ngon ngu + danh sach tool (da loc quyen).
    path("meta", views.AIMetaView.as_view(), name="ai-meta"),
    # JSON-RPC 2.0 cho tab MCP/Form: {method: "tools/list" | "tools/call"}.
    path("mcp", views.AIMCPView.as_view(), name="ai-mcp"),
    # Lich su phien chat (chi chinh user) + form dong cho tab Form.
    path("sessions", views.AIChatSessionListCreateView.as_view(), name="ai-sessions"),
    path("sessions/<uuid:session_id>/messages", views.AIChatSessionMessagesView.as_view(), name="ai-session-messages"),
    path("tools/<str:tool_name>/form", views.AIToolFormView.as_view(), name="ai-tool-form"),
]
