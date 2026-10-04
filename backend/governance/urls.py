from django.urls import path

from governance import views

urlpatterns = [
    path("rule-changes", views.ProposalListView.as_view()),
    path("rule-changes/<int:proposal_id>", views.ProposalDetailView.as_view()),
    path("rule-changes/<int:proposal_id>/withdraw", views.WithdrawView.as_view()),
    path("rule-changes/<int:proposal_id>/decision-code", views.DecisionCodeView.as_view()),
    path("rule-changes/<int:proposal_id>/decide", views.DecideView.as_view()),
]
