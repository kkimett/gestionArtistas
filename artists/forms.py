import re
import json
from decimal import Decimal, InvalidOperation

from django import forms
from django.core.exceptions import ValidationError

from .models import Artist, ArtistRecord, Grouping


class ArtistForm(forms.ModelForm):
    agrupaciones = forms.ModelMultipleChoiceField(
        queryset=Grouping.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={"size": 8}),
    )

    field_order = [
        "nombre_completo",
        "dni_nie",
        "irpf",
        "honorario",
        "telefono",
        "email",
        "prl",
        "agrupaciones",
        "cuenta_bancaria",
        "numero_seguridad_social",
    ]

    class Meta:
        model = Artist
        fields = [
            "nombre_completo",
            "dni_nie",
            "irpf",
            "honorario",
            "telefono",
            "email",
            "prl",
            "cuenta_bancaria",
            "numero_seguridad_social",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["agrupaciones"].queryset = Grouping.objects.order_by("nombre")
        if self.instance and self.instance.pk:
            self.fields["agrupaciones"].initial = self.instance.agrupaciones.all()

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

    def clean_honorario(self):
        value = self.cleaned_data.get("honorario")
        if value is None:
            return value
        if value < 0:
            raise ValidationError("El honorario no puede ser negativo.")
        if value > 100:
            raise ValidationError("El honorario no puede ser mayor de 100%.")
        return value

    def save(self, commit=True):
        instance = super().save(commit=commit)
        if commit:
            instance.agrupaciones.set(self.cleaned_data.get("agrupaciones", []))
        return instance


class ArtistRecordForm(forms.ModelForm):
    field_order = [
        "artista",
        "es_autonomo",
        "tipo_irpf",
        "fecha_alta",
        "fecha_baja",
        "solicitud_a1",
        "destino_a1",
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
        "estado_seguridad_social",
        "estado_facturacion",
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
            "destino_a1",
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
            "estado_seguridad_social",
            "estado_facturacion",
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
        self.fields["coste_empresa"].label = "Coste de la Empresa"

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

        solicitud_a1 = cleaned_data.get("solicitud_a1")
        destino_a1 = (cleaned_data.get("destino_a1") or "").strip()
        if solicitud_a1 and not destino_a1:
            self.add_error("destino_a1", "Indica el destino cuando la Solicitud A1 esté marcada.")
        if not solicitud_a1:
            cleaned_data["destino_a1"] = ""

        estado_pago = cleaned_data.get("estado_pago")
        estado_seguridad_social = cleaned_data.get("estado_seguridad_social")
        estado_facturacion = cleaned_data.get("estado_facturacion")
        importe_entregado = cleaned_data.get("importe_entregado")
        neto_para_pago = (cleaned_data.get("cache_neto") or 0) - (
            (cleaned_data.get("coste_empresa") or 0)
            + (cleaned_data.get("coste_gestion") or 0)
            + (cleaned_data.get("coste_seguridad_social") or 0)
            + (cleaned_data.get("coste_irpf") or 0)
        )

        if estado_pago == ArtistRecord.PaymentStatus.A_MEDIAS:
            if importe_entregado is None or importe_entregado <= 0:
                self.add_error("importe_entregado", "Indica el importe entregado cuando el estado es A medias.")
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


class GroupingRecordBatchForm(forms.Form):
    agrupacion = forms.ModelChoiceField(
        queryset=Grouping.objects.filter(activo=True).order_by("nombre"),
        label="Agrupación",
    )
    lineas = forms.CharField(widget=forms.HiddenInput(), required=False)
    fecha_alta = forms.DateField(widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}), label="Fecha alta")
    fecha_baja = forms.DateField(
        required=False,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
        label="Fecha baja",
    )
    proceso_cancelado = forms.BooleanField(required=False, label="Proceso cancelado")
    estado_pago = forms.ChoiceField(
        choices=ArtistRecord.PaymentStatus.choices,
        initial=ArtistRecord.PaymentStatus.PENDIENTE,
        label="Estado de pago",
    )
    observaciones = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}), label="Observaciones")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fecha_alta"].input_formats = ["%Y-%m-%d"]
        self.fields["fecha_baja"].input_formats = ["%Y-%m-%d"]

    def clean_lineas(self):
        raw_value = (self.cleaned_data.get("lineas") or "").strip()
        if not raw_value:
            raise ValidationError("Añade al menos un artista con su caché.")

        try:
            parsed = json.loads(raw_value)
        except json.JSONDecodeError as exc:
            raise ValidationError("No se pudieron interpretar las líneas de artistas.") from exc

        if not isinstance(parsed, list) or not parsed:
            raise ValidationError("Añade al menos una línea de artista.")

        normalized = []
        artist_ids = []
        repeated = set()
        seen = set()

        for index, item in enumerate(parsed, start=1):
            if not isinstance(item, dict):
                raise ValidationError(f"Línea {index}: formato inválido.")

            artist_id = str(item.get("artista_id", "")).strip()
            cache_raw = str(item.get("cache_neto", "")).strip().replace(",", ".")
            es_autonomo = bool(item.get("es_autonomo", False))
            solicitud_a1 = bool(item.get("solicitud_a1", False))
            destino_a1 = str(item.get("destino_a1", "")).strip()

            if not artist_id:
                raise ValidationError(f"Línea {index}: falta el artista.")
            if not cache_raw:
                raise ValidationError(f"Línea {index}: falta el caché neto.")

            try:
                cache_neto = Decimal(cache_raw)
            except InvalidOperation as exc:
                raise ValidationError(f"Línea {index}: el caché neto no es válido.") from exc

            if cache_neto <= 0:
                raise ValidationError(f"Línea {index}: el caché neto debe ser mayor que 0.")

            if solicitud_a1 and not destino_a1:
                raise ValidationError(f"Línea {index}: indica destino cuando Solicitud A1 está marcada.")
            if not solicitud_a1:
                destino_a1 = ""

            if artist_id in seen:
                repeated.add(artist_id)
            seen.add(artist_id)
            artist_ids.append(artist_id)
            normalized.append(
                {
                    "artista_id": artist_id,
                    "cache_neto": cache_neto,
                    "es_autonomo": es_autonomo,
                    "solicitud_a1": solicitud_a1,
                    "destino_a1": destino_a1,
                }
            )

        if repeated:
            raise ValidationError("Hay artistas repetidos en las líneas. Deja solo una línea por artista.")

        artists = Artist.objects.filter(pk__in=artist_ids)
        artists_map = {str(artist.pk): artist for artist in artists}
        if len(artists_map) != len(set(artist_ids)):
            raise ValidationError("Algunos artistas seleccionados ya no existen.")

        self.cleaned_data["lineas_normalizadas"] = [
            {
                "artista": artists_map[item["artista_id"]],
                "cache_neto": item["cache_neto"],
                "es_autonomo": item["es_autonomo"],
                "solicitud_a1": item["solicitud_a1"],
                "destino_a1": item["destino_a1"],
            }
            for item in normalized
        ]

        return raw_value

    def clean(self):
        cleaned_data = super().clean()

        fecha_alta = cleaned_data.get("fecha_alta")
        fecha_baja = cleaned_data.get("fecha_baja")
        if fecha_alta and fecha_baja and fecha_baja < fecha_alta:
            self.add_error("fecha_baja", "La fecha de baja no puede ser anterior a la fecha de alta.")

        return cleaned_data


class GroupingForm(forms.ModelForm):
    class Meta:
        model = Grouping
        fields = ["nombre", "descripcion", "activo", "artistas"]
        widgets = {
            "descripcion": forms.Textarea(attrs={"rows": 4}),
            "artistas": forms.SelectMultiple(attrs={"size": 12}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["artistas"].queryset = Artist.objects.order_by("nombre_completo")
        self.fields["artistas"].required = False
        self.selected_artist_ids = self._get_selected_artist_ids()

    def _get_selected_artist_ids(self):
        if self.is_bound:
            return [str(value) for value in self.data.getlist("artistas") if str(value).strip()]

        selected = self.initial.get("artistas")
        if selected is None and self.instance and self.instance.pk:
            selected = self.instance.artistas.values_list("pk", flat=True)
        if selected is None:
            return []

        if isinstance(selected, (str, int)):
            selected = [selected]

        normalized = []
        for value in selected:
            normalized.append(str(getattr(value, "pk", value)))
        return normalized

    def save(self, commit=True):
        return super().save(commit=commit)


class ArtistCSVUploadForm(forms.Form):
    csv_file = forms.FileField(label="Archivo CSV")

    def clean_csv_file(self):
        csv_file = self.cleaned_data["csv_file"]
        if not csv_file.name.lower().endswith(".csv"):
            raise ValidationError("Debes subir un archivo con extensión .csv")
        return csv_file