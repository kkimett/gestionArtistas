from django.contrib import admin

from .models import Invoice


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("referencia", "artista", "fecha_factura", "fecha_cobro", "importe", "estado")
    list_filter = ("estado", "fecha_factura", "fecha_cobro")
    search_fields = ("referencia", "artista__nombre_completo", "artista__dni_nie")
