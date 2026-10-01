from django.urls import include, path

from core.views import health

urlpatterns = [
    path("api/health", health),
    path("api/auth/", include("identity.urls")),
    path("api/", include("licensing.urls")),
    path("api/", include("reasons.urls")),
    path("api/", include("stock.urls")),
    path("api/", include("transactions.urls")),
]
