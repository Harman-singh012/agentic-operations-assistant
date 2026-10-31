import json

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from agent.core import run_agent
from .models import Conversation, Message

ERROR_TEXT = "Sorry, something went wrong. Click the three dots to see details."


def register(request):
    if request.user.is_authenticated:
        return redirect("home")
    form = UserCreationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("home")
    return render(request, "register.html", {"form": form})


@login_required
def home(request, cid=None):
    conversations = request.user.conversations.all()
    current = None
    messages = []
    if cid is not None:
        current = get_object_or_404(Conversation, id=cid, user=request.user)
        messages = current.messages.all()
    return render(
        request,
        "chat.html",
        {"conversations": conversations, "current": current, "messages": messages},
    )


def _sse(obj):
    return f"data: {json.dumps(obj)}\n\n"


@login_required
def stream(request):
    q = request.GET.get("q", "").strip()[:500]
    cid = request.GET.get("cid", "").strip()

    if not q:
        def empty():
            yield _sse({"type": "error", "text": "Please type a question."})
            yield _sse({"type": "done", "text": ""})
        return StreamingHttpResponse(empty(), content_type="text/event-stream")

    if cid.isdigit():
        conv = get_object_or_404(Conversation, id=int(cid), user=request.user)
    else:
        conv = Conversation.objects.create(user=request.user, title=q[:50])

    rows = conv.messages.order_by("-id")[:8]
    history = [(r.role, r.text) for r in reversed(list(rows))]
    Message.objects.create(conversation=conv, role="user", text=q)

    def events():
        yield _sse({"type": "meta", "cid": conv.id, "title": conv.title})
        steps = [{"type": "question", "text": q}]
        final = ""
        for ev in run_agent(q, history):
            if ev["type"] in ("action", "observation"):
                steps.append(ev)
                yield _sse(ev)
            elif ev["type"] == "error":
                steps.append(ev)
                yield _sse(ev)
                final = ERROR_TEXT
            elif ev["type"] == "final":
                final = ev["text"]
        if not final:
            final = "Sorry, I could not produce an answer."
        steps.append({"type": "final", "text": final})
        yield _sse({"type": "final", "text": final})
        Message.objects.create(conversation=conv, role="assistant", text=final, steps=steps)
        conv.save(update_fields=["updated"])
        yield _sse({"type": "done", "text": ""})

    resp = StreamingHttpResponse(events(), content_type="text/event-stream")
    resp["Cache-Control"] = "no-cache"
    resp["X-Accel-Buffering"] = "no"
    return resp


@login_required
@require_POST
def delete_chat(request, cid):
    get_object_or_404(Conversation, id=cid, user=request.user).delete()
    return JsonResponse({"ok": True})