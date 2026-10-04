from django.urls import path

from catalogue import views

urlpatterns = [
    path("catalogue/approval-thresholds", views.ApprovalThresholdListView.as_view()),
    path("catalogue/licence-types", views.LicenceTypeListView.as_view()),
    path("catalogue/classes", views.SubstanceClassListView.as_view()),
]
