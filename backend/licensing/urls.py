from django.urls import path

from licensing import views

urlpatterns = [
    path("enrolment/start", views.EnrolmentStartView.as_view()),
    path("enrolment/complete", views.EnrolmentCompleteView.as_view()),
    path("licences", views.LicenceRegisterView.as_view()),
    path("licences/mine", views.MyLicencesView.as_view()),
    path("licences/search", views.LicenceSearchView.as_view()),
    path("licences/<int:licence_id>", views.LicenceDetailView.as_view()),
    path("catalogue/substances", views.SubstanceListView.as_view()),
]
