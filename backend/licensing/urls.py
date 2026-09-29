from django.urls import path

from licensing import views

urlpatterns = [
    path("enrolment/start", views.EnrolmentStartView.as_view()),
    path("enrolment/complete", views.EnrolmentCompleteView.as_view()),
]
