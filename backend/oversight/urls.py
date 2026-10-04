from django.urls import path

from oversight import views

urlpatterns = [
    path("oversight/batches", views.BatchListView.as_view()),
    path("oversight/batches/<int:batch_id>", views.BatchDetailView.as_view()),
    path("oversight/batches/<int:batch_id>/flag", views.FlagView.as_view()),
    path("oversight/batches/<int:batch_id>/sign-off-code", views.SignOffCodeView.as_view()),
    path("oversight/batches/<int:batch_id>/sign-off", views.SignOffView.as_view()),
    path("oversight/review-settings", views.ReviewSettingsView.as_view()),
    path("oversight/review-settings/<int:position_id>", views.ReviewSettingChangeView.as_view()),
]
