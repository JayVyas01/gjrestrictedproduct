from django.urls import path

from licensing import views

urlpatterns = [
    path("enrolment/start", views.EnrolmentStartView.as_view()),
    path("enrolment/complete", views.EnrolmentCompleteView.as_view()),
    path("licences/mine", views.MyLicencesView.as_view()),
    path("catalogue/substances", views.SubstanceListView.as_view()),
]
