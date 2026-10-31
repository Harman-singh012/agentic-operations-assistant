from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("c/<int:cid>/", views.home, name="conversation"),
    path("stream/", views.stream, name="stream"),
    path("delete/<int:cid>/", views.delete_chat, name="delete_chat"),
    path("login/", auth_views.LoginView.as_view(template_name="login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("register/", views.register, name="register"),
]