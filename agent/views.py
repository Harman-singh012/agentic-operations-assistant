import json
import logging

from django.http import StreamingHttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework.negotiation import BaseContentNegotiation
from rest_framework.renderers import JSONRenderer
from rest_framework.views import APIView

from .graph import run_agent_events
from .serializers import ChatRequestSerializer

logger = logging.getLogger(__name__)


class IgnoreClientContentNegotiation(BaseContentNegotiation):
    """Lets the browser send `Accept: text/event-stream` without DRF answering 406."""

    def select_parser(self, request, parsers):
        return parsers[0]

    def select_renderer(self, request, renderers, format_suffix=None):
        return renderers[0], renderers[0].media_type


def sse(event: str, data: dict) -> str:
    # json.dumps never emits raw newlines, so one `data:` line is always safe.
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@ensure_csrf_cookie
def chat_page(request):
    return render(request, "chat.html")


class ChatStreamView(APIView):
    renderer_classes = [JSONRenderer]
    content_negotiation_class = IgnoreClientContentNegotiation

    def post(self, request):
        ser = ChatRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        message, thread_id = ser.validated_data["message"], ser.validated_data["thread_id"]

        def stream():
            yield sse("start", {"thread_id": thread_id})
            try:
                for event, data in run_agent_events(message, thread_id):
                    yield sse(event, data)
            except Exception:
                logger.exception("Agent run failed")
                yield sse("error", {"message": "The assistant hit an error. Check the server log and try again."})
            yield sse("done", {})

        response = StreamingHttpResponse(stream(), content_type="text/event-stream")
        response["Cache-Control"] = "no-cache"
        response["X-Accel-Buffering"] = "no"  # stop nginx from buffering the stream
        return response
