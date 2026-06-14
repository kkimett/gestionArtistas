import re

from django import forms
from django.core.exceptions import ValidationError

from .models import Artist, ArtistRecord, Grouping


class ArtistForm(forms.ModelForm):
    field_order = [
        "nombre_completo",
        "dni_nie",
        "cuenta_bancaria",
        "numero_seguridad_social",
    ]

    class Meta:
        model = Artist
        fields = [
            "nombre_completo",
            "dni_nie",
            "cuenta_bancaria",
            "numero_seguridad_social",
        ]

    def clean_dni_nie(self):
        value = self.cleaned_data["dni_nie"].strip().upper()
        dni_pattern = re.compile(r"^\d{8}[A-Z]$")
        nie_pattern = re.compile(r"^[XYZ]\d{7}[A-Z]$")
        letters = "TRWAGMYFPDXBNJZSQVHLCKE"

        if dni_pattern.match(value):
            number = int(value[:8])
            expected_letter = letters[number % 23]
            if value[-1] != expected_letter:
                raise ValidationError("El DNI no tiene una letra válida.")
            return value

        if nie_pattern.match(value):
            translated = value.replace("X", "0", 1).replace("Y", "1", 1).replace("Z", "2", 1)
            number = int(translated[:8])
            expected_letter = letters[number % 23]
            if value[-1] != expected_letter:
                raise ValidationError("El NIE no tiene una letra válida.")
            return value

        raise ValidationError("El DNI/NIE debe tener un formato válido.")

    def clean_cuenta_bancaria(self):
        value = self.cleaned_data.get("cuenta_bancaria", "").replace(" ", "").upper()
        if not value:
            return value

        iban_pattern = re.compile(r"^[A-Z]{2}\d{2}[A-Z0-9]{11,30}$")
        if not iban_pattern.match(value):
            raise ValidationError("El número de cuenta debe tener formato IBAN válido.")

        rearranged = value[4:] + value[:4]
        numeric = ""
        for char in rearranged:
            numeric += char if char.isdigit() else str(ord(char) - 55)

        remainder = 0
        for digit in numeric:
            remainder = (remainder * 10 + int(digit)) % 97

        if remainder != 1:
            raise ValidationError("El IBAN no es válido.")

        return value


class ArtistRecordForm(forms.ModelForm):
    field_order = [
        "artista",
        "es_autonomo",
        "tipo_irpf",
        "fecha_alta",
        "fecha_baja",
        "solicitud_a1",
        "proceso_cancelado",
        "tipo_registro",
        "agrupacion",
        "cache_neto",
        "coste_empresa",
        "coste_gestion",
        "coste_seguridad_social",
        "coste_irpf",
        "importe_entregado",
        "estado_pago",
        "observaciones",
    ]

    class Meta:
        model = ArtistRecord
        fields = [
            "artista",
            "es_autonomo",
            "tipo_irpf",
            "fecha_alta",
            "fecha_baja",
            "solicitud_a1",
            "proceso_cancelado",
            "tipo_registro",
            "agrupacion",
            "cache_neto",
            "coste_empresa",
            "coste_gestion",
            "coste_seguridad_social",
            "coste_irpf",
            "importe_entregado",
            "estado_pago",
            "observaciones",
        ]
        widgets = {
            "fecha_alta": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "fecha_baja": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            "observaciones": forms.Textarea(attrs={"rows": 4}),
            "coste_empresa": forms.NumberInput(attrs={"readonly": True}),
            "coste_gestion": forms.NumberInput(attrs={"readonly": True}),
            "coste_seguridad_social": forms.NumberInput(attrs={"readonly": True}),
            "coste_irpf": forms.NumberInput(attrs={"readonly": True}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # El navegador para input type=date usa YYYY-MM-DD.
        self.fields["fecha_alta"].input_formats = ["%Y-%m-%d"]
        self.fields["fecha_baja"].input_formats = ["%Y-%m-%d"]

        # Se muestran como solo lectura, pero deben enviarse para validar correctamente.
        for field_name in (
            "coste_empresa",
            "coste_gestion",
            "coste_seguridad_social",
            "coste_irpf",
        ):
            self.fields[field_name].required = True
            self.fields[field_name].disabled = False
            self.fields[field_name].widget.attrs["readonly"] = True

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("es_autonomo") and not cleaned_data.get("tipo_irpf"):
            self.add_error("tipo_irpf", "Debes indicar un tipo de IRPF para autónomos.")

        estado_pago = cleaned_data.get("estado_pago")
        importe_entregado = cleaned_data.get("importe_entregado")
        neto_para_pago = (cleaned_data.get("cache_neto") or 0) - (
            (cleaned_data.get("coste_empresa") or 0)
            + (cleaned_data.get("coste_gestion") or 0)
            + (cleaned_data.get("coste_seguridad_social") or 0)
            + (cleaned_data.get("coste_irpf") or 0)
        )

        if estado_pago == ArtistRecord.PaymentStatus.PARTIAL:
            if importe_entregado is None or importe_entregado <= 0:
                self.add_error("importe_entregado", "Indica el importe entregado cuando el estado es Pago a Medias.")
            elif importe_entregado >= neto_para_pago:
                self.add_error("importe_entregado", "El importe entregado debe ser menor al neto pendiente por pagar.")

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Calcular automáticamente los costos según el tramo
        instance.calculate_and_update_costs()
        if commit:
            instance.save()
        return instance


class GroupingForm(forms.ModelForm):
    class Meta:
        model = Grouping
        fields = ["nombre", "descripcion", "activo"]
        widgets = {
            "descripcion": forms.Textarea(attrs={"rows": 4}),
        }


class ArtistCSVUploadForm(forms.Form):
    csv_file = forms.FileField(label="Archivo CSV")

    def clean_csv_file(self):
        csv_file = self.cleaned_data["csv_file"]
        if not csv_file.name.lower().endswith(".csv"):
            raise ValidationError("Debes subir un archivo con extensión .csv")
        return csv_file