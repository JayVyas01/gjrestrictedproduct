from django.urls import path

from demo import views

urlpatterns = [
    path("inbox", views.InboxView.as_view()),
    path("personas", views.PersonasView.as_view()),
    path("signup/start", views.SignupStartView.as_view()),
    path("signup/complete", views.SignupCompleteView.as_view()),
    path("signup/candidates", views.SignupCandidatesView.as_view()),
]
