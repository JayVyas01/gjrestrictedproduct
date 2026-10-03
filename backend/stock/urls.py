from django.urls import path

from stock import views

urlpatterns = [path("stock/mine", views.MyStockView.as_view())]
