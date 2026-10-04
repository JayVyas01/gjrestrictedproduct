from django.urls import path

from transactions import views

urlpatterns = [
    path("transactions", views.TransactionListView.as_view()),
    path("transactions/buyer-lookup", views.BuyerLookupView.as_view()),
    path("transactions/check", views.CheckView.as_view()),
    path("transactions/<str:reference>", views.TransactionDetailView.as_view()),
    path("transactions/<str:reference>/decision-code", views.DecisionCodeView.as_view()),
    path("transactions/<str:reference>/decide", views.DecideView.as_view()),
    path("transactions/<str:reference>/cancel", views.CancelView.as_view()),
]
