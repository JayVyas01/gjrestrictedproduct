from django.urls import path

from oversight import views

urlpatterns = [
    path("oversight/batches", views.BatchListView.as_view()),
    path("oversight/batches/<int:batch_id>", views.BatchDetailView.as_view()),
    path("oversight/batches/<int:batch_id>/flag", views.FlagView.as_view()),
    path("oversight/batches/<int:batch_id>/sign-off-code", views.SignOffCodeView.as_view()),
    path("oversight/batches/<int:batch_id>/sign-off", views.SignOffView.as_view()),
]
