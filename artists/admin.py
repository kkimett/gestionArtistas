from django.contrib import admin
from django import forms

from .models import Artist, ArtistRecord, CostPercentageSettings, Grouping, GroupingRecordBatch, PriceBracket


@admin.register(Grouping)
class GroupingAdmin(admin.ModelAdmin):
    list_display = ("nombre", "activo", "creado_en")
    list_filter = ("activo",)
    search_fields = ("nombre",)


class PriceBracketAdminForm(forms.ModelForm):
    class Meta:
        model = PriceBracket
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["importe_base"].help_text = (
            "Para el tramo 1 no se usa una base fija: el cálculo toma el caché neto del registro."
        )

    def clean(self):
        cleaned_data = super().clean()
        numero_tramo = cleaned_data.get("numero_tramo")

        if numero_tramo == 1:
            cleaned_data["rango_minimo"] = 0
            cleaned_data["importe_base"] = None

        return cleaned_data


@admin.register(PriceBracket)
class PriceBracketAdmin(admin.ModelAdmin):
    form = PriceBracketAdminForm
    list_display = (
        "numero_tramo",
        "rango_minimo",
        "rango_maximo",
        "importe_base",
        "activo",
    )
    list_filter = ("activo", "numero_tramo")
    fieldsets = (
        ("Información del Tramo", {
            "fields": ("numero_tramo", "rango_minimo", "rango_maximo", "importe_base", "activo")
            ,"description": "En el tramo 1, el rango mínimo debe ser 0 y la base se calcula con el caché neto del registro."
        }),
    )


@admin.register(CostPercentageSettings)
class CostPercentageSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "porcentaje_honorarios",
        "actualizado_en",
    )
    readonly_fields = ("actualizado_en",)
    fieldsets = (
        ("Contingencias comunes", {
            "fields": ("contingencias_comunes_empresa", "contingencias_comunes_trabajador"),
        }),
        ("MEI", {
            "fields": ("mei_empresa", "mei_trabajador"),
        }),
        ("Desempleo", {
            "fields": ("desempleo_empresa", "desempleo_trabajador"),
        }),
        ("Formación", {
            "fields": ("formacion_empresa", "formacion_trabajador"),
        }),
        ("AT y EP", {
            "fields": ("at_ep_empresa",),
        }),
        ("Fondo de garantía salarial", {
            "fields": ("fogasa_empresa",),
        }),
        ("Honorarios", {
            "fields": ("porcentaje_honorarios",),
        }),
        ("Auditoría", {
            "fields": ("actualizado_en",),
        }),
    )

    def has_add_permission(self, request):
        return not CostPercentageSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Artist)
class ArtistAdmin(admin.ModelAdmin):
    list_display = (
        "nombre_completo",
        "dni_nie",
        "irpf",
        "honorario",
        "telefono",
        "email",
        "prl",
        "get_agrupaciones",
        "numero_seguridad_social",
        "cuenta_bancaria",
        "creado_en",
    )
    search_fields = (
        "nombre_completo",
        "dni_nie",
        "telefono",
        "email",
        "numero_seguridad_social",
        "cuenta_bancaria",
        "agrupaciones__nombre",
    )
    readonly_fields = ("creado_en", "actualizado_en")
    fieldsets = (
        ("Información Personal", {
            "fields": ("nombre_completo", "dni_nie", "irpf", "honorario", "telefono", "email", "prl")
        }),
        ("Datos Bancarios", {
            "fields": ("cuenta_bancaria", "numero_seguridad_social")
        }),
        ("Auditoría", {
            "fields": ("creado_en", "actualizado_en"),
            "classes": ("collapse",)
        }),
    )
    def get_agrupaciones(self, obj):
        return ", ".join(obj.agrupaciones.values_list("nombre", flat=True)) or "-"

    get_agrupaciones.short_description = "Agrupaciones"


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
            "fields": ("es_autonomo", "tipo_irpf", "solicitud_a1", "destino_a1")
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


@admin.register(GroupingRecordBatch)
class GroupingRecordBatchAdmin(admin.ModelAdmin):
    list_display = ("agrupacion", "estado", "fecha_alta", "estado_pago", "creado_en", "generado_en")
    list_filter = ("estado", "estado_pago", "proceso_cancelado", "agrupacion")
    search_fields = ("agrupacion__nombre", "observaciones")
    readonly_fields = ("creado_en", "actualizado_en", "generado_en")
