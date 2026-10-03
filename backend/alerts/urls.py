from django.urls import path

from alerts import views

urlpatterns = [
    path("alerts", views.AlertListView.as_view()),
    path("alerts/<int:alert_id>/acknowledge", views.AcknowledgeView.as_view()),
]
