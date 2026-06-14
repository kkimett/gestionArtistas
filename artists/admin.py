from django.contrib import admin

from .models import Artist, ArtistRecord, Grouping, PriceBracket


@admin.register(Grouping)
class GroupingAdmin(admin.ModelAdmin):
    list_display = ("nombre", "activo", "creado_en")
    list_filter = ("activo",)
    search_fields = ("nombre",)


@admin.register(PriceBracket)
class PriceBracketAdmin(admin.ModelAdmin):
    list_display = (
        "numero_tramo",
        "rango_minimo",
        "rango_maximo",
        "importe_base",
        "porcentaje_empresa",
        "porcentaje_gestion",
        "porcentaje_seguridad_social",
        "porcentaje_irpf",
        "activo",
    )
    list_filter = ("activo", "numero_tramo")
    fieldsets = (
        ("Información del Tramo", {
            "fields": ("numero_tramo", "rango_minimo", "rango_maximo", "importe_base", "activo")
        }),
        ("Porcentajes de Costos", {
            "fields": (
                "porcentaje_empresa",
                "porcentaje_gestion",
                "porcentaje_seguridad_social",
                "porcentaje_irpf",
            )
        }),
    )


@admin.register(Artist)
class ArtistAdmin(admin.ModelAdmin):
    list_display = (
        "nombre_completo",
        "dni_nie",
        "numero_seguridad_social",
        "cuenta_bancaria",
        "creado_en",
    )
    search_fields = ("nombre_completo", "dni_nie", "numero_seguridad_social", "cuenta_bancaria")
    readonly_fields = ("creado_en", "actualizado_en")
    fieldsets = (
        ("Información Personal", {
            "fields": ("nombre_completo", "dni_nie", "numero_seguridad_social")
        }),
        ("Datos Bancarios", {
            "fields": ("cuenta_bancaria",)
        }),
        ("Auditoría", {
            "fields": ("creado_en", "actualizado_en"),
            "classes": ("collapse",)
        }),
    )


@admin.register(ArtistRecord)
class ArtistRecordAdmin(admin.ModelAdmin):
    list_display = (
        "artista",
        "tipo_registro",
        "fecha_alta",
        "cache_neto",
        "coste_total",
        "importe_entregado",
        "importe_pendiente",
        "estado_pago",
        "agrupacion",
    )
    list_filter = ("tipo_registro", "estado_pago", "es_autonomo", "agrupacion")
    search_fields = ("artista__nombre_completo", "artista__dni_nie", "artista__numero_seguridad_social")
    readonly_fields = (
        "coste_empresa",
        "coste_gestion",
        "coste_seguridad_social",
        "coste_irpf",
        "coste_total",
        "neto_para_pago",
        "importe_pendiente",
        "creado_en",
        "actualizado_en",
    )
    fieldsets = (
        ("Artista", {
            "fields": ("artista", "tipo_registro", "agrupacion")
        }),
        ("Configuración Tributaria", {
            "fields": ("es_autonomo", "tipo_irpf", "solicitud_a1")
        }),
        ("Altas y Bajas", {
            "fields": ("fecha_alta", "fecha_baja", "proceso_cancelado")
        }),
        ("Caché y Costos (Cache Neto)", {
            "fields": ("cache_neto",),
            "description": "Ingresa solo el caché neto. Los costos se calcularán automáticamente según el tramo."
        }),
        ("Costos Calculados", {
            "fields": (
                "coste_empresa",
                "coste_gestion",
                "coste_seguridad_social",
                "coste_irpf",
                "coste_total",
                "neto_para_pago",
            ),
            "description": "Estos campos se calculan automáticamente según el tramo de precios.",
            "classes": ("collapse",)
        }),
        ("Estado de Pago", {
            "fields": ("estado_pago", "importe_entregado", "importe_pendiente", "observaciones")
        }),
        ("Auditoría", {
            "fields": ("creado_en", "actualizado_en"),
            "classes": ("collapse",)
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return self.readonly_fields
        return ()

    def save_model(self, request, obj, form, change):
        obj.calculate_and_update_costs()
        super().save_model(request, obj, form, change)
