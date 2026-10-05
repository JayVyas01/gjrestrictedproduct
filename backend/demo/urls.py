from django.urls import path

from demo import views

urlpatterns = [
    path("inbox", views.InboxView.as_view()),
    path("personas", views.PersonasView.as_view()),
]
