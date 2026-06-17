from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from artists.models import ArtistRecord


class PaymentSummaryView(LoginRequiredMixin, TemplateView):
    template_name = "billing/payment_summary.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        paid_records = ArtistRecord.objects.select_related("artista", "agrupacion").filter(
            estado_pago=ArtistRecord.PaymentStatus.ABONADO,
        ).order_by("-actualizado_en")
        total_paid_records = sum(record.importe_entregado or record.neto_para_pago for record in paid_records)

        context["paid_records"] = paid_records
        context["total_paid"] = total_paid_records
        return context
