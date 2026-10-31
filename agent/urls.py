from django.urls import path

from .views import ChatStreamView, chat_page

urlpatterns = [
    path("", chat_page, name="chat"),
    path("api/chat/stream/", ChatStreamView.as_view(), name="chat-stream"),
]
