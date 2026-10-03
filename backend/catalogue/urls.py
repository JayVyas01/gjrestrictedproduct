from django.urls import path

from catalogue import views

urlpatterns = [
    path("catalogue/approval-thresholds", views.ApprovalThresholdListView.as_view()),
]
