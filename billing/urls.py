from django.urls import path

from .views import PaymentSummaryView

app_name = "billing"

urlpatterns = [
    path("payments/today/", PaymentSummaryView.as_view(), name="payment-summary"),
]
