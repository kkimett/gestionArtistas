import csv
import io
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from .forms import ArtistCSVUploadForm, ArtistForm, ArtistRecordForm, GroupingForm
from .models import Artist, ArtistRecord, Grouping, PriceBracket


@login_required
def calcular_costes_por_tramo(request):
    cache_neto = request.GET.get("cache_neto", "").strip()
    if not cache_neto:
        return JsonResponse({"ok": False, "error": "Debes indicar un caché neto."}, status=400)

    try:
        importe_cache_neto = Decimal(cache_neto)
    except InvalidOperation:
        return JsonResponse({"ok": False, "error": "El caché neto no tiene un formato válido."}, status=400)

    if importe_cache_neto <= 0:
        return JsonResponse({"ok": False, "error": "El caché neto debe ser mayor que 0."}, status=400)

    tramo = PriceBracket.get_bracket_for_amount(importe_cache_neto)
    if not tramo:
        return JsonResponse({"ok": False, "error": "No existe un tramo activo para ese caché neto."}, status=404)

    costes = tramo.calculate_costs(importe_cache_neto)
    return JsonResponse(
        {
            "ok": True,
            "tramo": tramo.numero_tramo,
            "rango": f"{tramo.rango_minimo} - {tramo.rango_maximo}",
            "costes": {
                "coste_empresa": f"{costes['coste_empresa']:.2f}",
                "coste_gestion": f"{costes['coste_gestion']:.2f}",
                "coste_seguridad_social": f"{costes['coste_seguridad_social']:.2f}",
                "coste_irpf": f"{costes['coste_irpf']:.2f}",
            },
        }
    )


class ArtistListView(LoginRequiredMixin, ListView):
    model = Artist
    template_name = "artists/artist_list.html"
    context_object_name = "artists"

    def get_queryset(self):
        queryset = super().get_queryset().annotate(total_registros=Count("registros"))
        query = self.request.GET.get("q", "").strip()

        if query:
            queryset = queryset.filter(
                Q(nombre_completo__icontains=query)
                | Q(dni_nie__icontains=query)
                | Q(numero_seguridad_social__icontains=query)
                | Q(cuenta_bancaria__icontains=query)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter_values"] = {
            "q": self.request.GET.get("q", ""),
        }
        return context


class ArtistRecordListView(LoginRequiredMixin, ListView):
    model = ArtistRecord
    template_name = "artists/artist_record_list.html"
    context_object_name = "records"

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .select_related("artista", "agrupacion")
            .exclude(estado_pago=ArtistRecord.PaymentStatus.PAID)
        )
        query = self.request.GET.get("q", "").strip()
        status = self.request.GET.get("estado", "").strip()
        registration_type = self.request.GET.get("tipo_registro", "").strip()
        grouping = self.request.GET.get("agrupacion", "").strip()
        artist_id = self.request.GET.get("artista", "").strip()
        date_from = self.request.GET.get("fecha_desde", "").strip()
        date_to = self.request.GET.get("fecha_hasta", "").strip()

        if query:
            queryset = queryset.filter(
                Q(artista__nombre_completo__icontains=query)
                | Q(artista__dni_nie__icontains=query)
                | Q(artista__numero_seguridad_social__icontains=query)
            )
        if status and status != ArtistRecord.PaymentStatus.PAID:
            queryset = queryset.filter(estado_pago=status)
        if registration_type:
            queryset = queryset.filter(tipo_registro=registration_type)
        if grouping:
            queryset = queryset.filter(agrupacion_id=grouping)
        if artist_id:
            queryset = queryset.filter(artista_id=artist_id)
        if date_from:
            queryset = queryset.filter(fecha_alta__gte=date_from)
        if date_to:
            queryset = queryset.filter(fecha_alta__lte=date_to)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["groupings"] = Grouping.objects.filter(activo=True).order_by("nombre")
        context["artists_for_filter"] = Artist.objects.order_by("nombre_completo")
        context["payment_status_choices"] = [
            choice
            for choice in ArtistRecord.PaymentStatus.choices
            if choice[0] != ArtistRecord.PaymentStatus.PAID
        ]
        context["registration_type_choices"] = ArtistRecord.RegistrationType.choices
        context["filter_values"] = {
            "q": self.request.GET.get("q", ""),
            "estado": self.request.GET.get("estado", ""),
            "tipo_registro": self.request.GET.get("tipo_registro", ""),
            "agrupacion": self.request.GET.get("agrupacion", ""),
            "artista": self.request.GET.get("artista", ""),
            "fecha_desde": self.request.GET.get("fecha_desde", ""),
            "fecha_hasta": self.request.GET.get("fecha_hasta", ""),
        }
        return context


class ArtistCreateView(LoginRequiredMixin, CreateView):
    model = Artist
    form_class = ArtistForm
    template_name = "artists/artist_form.html"
    success_url = reverse_lazy("artists:list")


@login_required
def artist_bulk_upload_view(request):
    required_columns = [
        "nombre_completo",
        "dni_nie",
        "cuenta_bancaria",
        "numero_seguridad_social",
    ]
    form = ArtistCSVUploadForm(request.POST or None, request.FILES or None)
    context = {
        "form": form,
        "required_columns": required_columns,
        "created_count": 0,
        "processed_count": 0,
        "error_rows": [],
    }

    if request.method == "POST" and form.is_valid():
        csv_file = form.cleaned_data["csv_file"]
        try:
            raw_data = csv_file.read()
            try:
                decoded_data = raw_data.decode("utf-8-sig")
            except UnicodeDecodeError:
                decoded_data = raw_data.decode("latin-1")
        except UnicodeDecodeError:
            form.add_error("csv_file", "No se pudo leer el archivo. Usa codificación UTF-8 o Latin-1.")
            return render(request, "artists/artist_bulk_upload.html", context)

        reader = csv.DictReader(io.StringIO(decoded_data))
        if not reader.fieldnames:
            form.add_error("csv_file", "El CSV está vacío o no tiene cabecera.")
            return render(request, "artists/artist_bulk_upload.html", context)

        normalized_headers = {header.strip().lower() for header in reader.fieldnames if header}
        missing_columns = [column for column in required_columns if column not in normalized_headers]
        if missing_columns:
            form.add_error(
                "csv_file",
                "Faltan columnas obligatorias: " + ", ".join(missing_columns),
            )
            return render(request, "artists/artist_bulk_upload.html", context)

        created_count = 0
        processed_count = 0
        error_rows = []

        for row_number, row in enumerate(reader, start=2):
            normalized_row = {(key or "").strip().lower(): (value or "").strip() for key, value in row.items()}
            if not any(normalized_row.values()):
                continue

            processed_count += 1
            artist_form = ArtistForm(
                data={
                    "nombre_completo": normalized_row.get("nombre_completo", ""),
                    "dni_nie": normalized_row.get("dni_nie", ""),
                    "cuenta_bancaria": normalized_row.get("cuenta_bancaria", ""),
                    "numero_seguridad_social": normalized_row.get("numero_seguridad_social", ""),
                }
            )

            if artist_form.is_valid():
                artist_form.save()
                created_count += 1
            else:
                error_rows.append(
                    {
                        "line": row_number,
                        "errors": artist_form.errors,
                    }
                )

        context.update(
            {
                "created_count": created_count,
                "processed_count": processed_count,
                "error_rows": error_rows,
            }
        )

    return render(request, "artists/artist_bulk_upload.html", context)


class ArtistUpdateView(LoginRequiredMixin, UpdateView):
    model = Artist
    form_class = ArtistForm
    template_name = "artists/artist_form.html"
    success_url = reverse_lazy("artists:list")


class ArtistRecordCreateView(LoginRequiredMixin, CreateView):
    model = ArtistRecord
    form_class = ArtistRecordForm
    template_name = "artists/artist_record_form.html"
    success_url = reverse_lazy("artists:record-list")

    def get_initial(self):
        initial = super().get_initial()
        artista = self.request.GET.get("artista")
        agrupacion_creada = self.request.GET.get("agrupacion_creada")
        if artista:
            initial["artista"] = artista
        if agrupacion_creada:
            initial["agrupacion"] = agrupacion_creada
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["ruta_actual"] = self.request.get_full_path()
        return context


class ArtistRecordUpdateView(LoginRequiredMixin, UpdateView):
    model = ArtistRecord
    form_class = ArtistRecordForm
    template_name = "artists/artist_record_form.html"
    success_url = reverse_lazy("artists:record-list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["ruta_actual"] = self.request.get_full_path()
        return context


class ArtistDeleteView(LoginRequiredMixin, DeleteView):
    model = Artist
    template_name = "artists/artist_confirm_delete.html"
    success_url = reverse_lazy("artists:list")


class ArtistRecordDeleteView(LoginRequiredMixin, DeleteView):
    model = ArtistRecord
    template_name = "artists/artist_record_confirm_delete.html"
    success_url = reverse_lazy("artists:record-list")


class GroupingCreateView(LoginRequiredMixin, CreateView):
    model = Grouping
    form_class = GroupingForm
    template_name = "artists/grouping_form.html"
    success_url = reverse_lazy("artists:list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["next"] = self.request.GET.get("next", "")
        return context

    def get_success_url(self):
        next_url = self.request.POST.get("next") or self.request.GET.get("next")
        if next_url:
            separator = "&" if "?" in next_url else "?"
            return f"{next_url}{separator}{urlencode({'agrupacion_creada': self.object.pk})}"
        return self.success_url
