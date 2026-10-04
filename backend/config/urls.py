from django.urls import include, path

from core.views import HomeView, health

urlpatterns = [
    path("api/health", health),
    path("api/auth/", include("identity.urls")),
    path("api/home", HomeView.as_view()),
    path("api/", include("catalogue.urls")),
    path("api/", include("licensing.urls")),
    path("api/", include("reasons.urls")),
    path("api/", include("stock.urls")),
    path("api/", include("transactions.urls")),
    path("api/", include("alerts.urls")),
    path("api/", include("oversight.urls")),
    path("api/", include("governance.urls")),
]
