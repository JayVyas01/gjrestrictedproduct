from django.urls import path

from reasons import views

urlpatterns = [path("reason-codes", views.ReasonCodeListView.as_view())]
