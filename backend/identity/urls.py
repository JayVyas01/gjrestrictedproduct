from django.urls import path

from identity import views

urlpatterns = [
    path("csrf", views.CsrfView.as_view()),
    path("login", views.LoginStartView.as_view()),
    path("login/verify", views.LoginVerifyView.as_view()),
    path("logout", views.LogoutView.as_view()),
    path("me", views.MeView.as_view()),
]
