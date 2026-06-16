import csv
import io
import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Count, Max, Q
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, FormView, ListView, TemplateView, UpdateView

from .forms import ArtistCSVUploadForm, ArtistForm, ArtistRecordForm, GroupingForm, GroupingRecordBatchForm
from .models import Artist, ArtistRecord, CostPercentageSettings, Grouping, PriceBracket


def calcular_num_dias(fecha_alta_raw, fecha_baja_raw):
    if not fecha_alta_raw:
        return Decimal("1")

    try:
        fecha_alta = datetime.strptime(fecha_alta_raw, "%Y-%m-%d").date()
    except ValueError:
        return Decimal("1")

    if not fecha_baja_raw:
        return Decimal("1")

    try:
        fecha_baja = datetime.strptime(fecha_baja_raw, "%Y-%m-%d").date()
    except ValueError:
        return Decimal("1")

    diferencia = (fecha_baja - fecha_alta).days + 1
    return Decimal(diferencia if diferencia > 0 else 1)


@login_required
def calcular_costes_por_tramo(request):
    cache_neto = request.GET.get("cache_neto", "").strip()
    tipo_irpf = request.GET.get("tipo_irpf", "").strip()
    artista_id = request.GET.get("artista", "").strip()
    tipo_registro = request.GET.get("tipo_registro", "").strip()
    agrupacion_id = request.GET.get("agrupacion", "").strip()
    contexto_calculo = request.GET.get("contexto", "registro").strip()
    fecha_alta_raw = request.GET.get("fecha_alta", "").strip()
    fecha_baja_raw = request.GET.get("fecha_baja", "").strip()
    num_dias_raw = request.GET.get("num_dias", "").strip()
    n_artistas_raw = request.GET.get("n_artistas", "").strip()
    honorario_artista = None
    if not cache_neto:
        return JsonResponse({"ok": False, "error": "Debes indicar un caché neto."}, status=400)

    try:
        importe_cache_neto = Decimal(cache_neto)
    except InvalidOperation:
        return JsonResponse({"ok": False, "error": "El caché neto no tiene un formato válido."}, status=400)

    if importe_cache_neto <= 0:
        return JsonResponse({"ok": False, "error": "El caché neto debe ser mayor que 0."}, status=400)

    porcentaje_irpf = None
    if tipo_irpf:
        try:
            porcentaje_irpf = Decimal(tipo_irpf)
        except InvalidOperation:
            return JsonResponse({"ok": False, "error": "El tipo de IRPF no tiene un formato válido."}, status=400)
        if porcentaje_irpf < 0:
            return JsonResponse({"ok": False, "error": "El tipo de IRPF no puede ser negativo."}, status=400)

    porcentajes = CostPercentageSettings.get_solo()
    cantidad_artistas = Decimal("1")
    if artista_id:
        artista = Artist.objects.filter(pk=artista_id).first()
        if artista and artista.honorario is not None:
            honorario_artista = artista.honorario

    if n_artistas_raw:
        try:
            n_artistas_val = int(n_artistas_raw)
            if n_artistas_val > 0:
                cantidad_artistas = Decimal(n_artistas_val)
        except (ValueError, TypeError):
            pass
    elif contexto_calculo == "agrupacion" and tipo_registro == ArtistRecord.RegistrationType.BAND and agrupacion_id:
        try:
            agrupacion = Grouping.objects.filter(pk=agrupacion_id).first()
            if agrupacion:
                total = agrupacion.artistas.count()
                if total > 0:
                    cantidad_artistas = Decimal(total)
        except Exception:
            cantidad_artistas = Decimal("1")

    if num_dias_raw:
        try:
            num_dias_val = int(num_dias_raw)
            num_dias = Decimal(num_dias_val if num_dias_val > 0 else 1)
        except (ValueError, TypeError):
            num_dias = calcular_num_dias(fecha_alta_raw, fecha_baja_raw)
    else:
        num_dias = calcular_num_dias(fecha_alta_raw, fecha_baja_raw)
    porcentaje_empresa_total = (
        porcentajes.contingencias_comunes_empresa
        + porcentajes.mei_empresa
        + porcentajes.desempleo_empresa
        + porcentajes.formacion_empresa
        + porcentajes.at_ep_empresa
        + porcentajes.fogasa_empresa
    )

    tramo = PriceBracket.get_bracket_for_calculator(
        importe_cache_neto,
        num_days=num_dias,
        n_artistas=cantidad_artistas,
        porcentaje_empresa_total=porcentaje_empresa_total,
    )
    if not tramo:
        return JsonResponse({"ok": False, "error": "No existe un tramo activo para ese cálculo."}, status=404)

    costes = tramo.calculate_costs(
        importe_cache_neto,
        irpf_percentage=porcentaje_irpf,
        honorarios_percentage=honorario_artista,
        num_days=num_dias,
        n_artistas=cantidad_artistas,
    )
    base_cotizacion = costes["base_cotizacion"]
    salario_bruto = costes["salario_bruto"]

    detalle_ss = {
        "contingencias_comunes_empresa": {
            "porcentaje": porcentajes.contingencias_comunes_empresa,
            "importe": base_cotizacion * (porcentajes.contingencias_comunes_empresa / Decimal("100")),
        },
        "contingencias_comunes_trabajador": {
            "porcentaje": porcentajes.contingencias_comunes_trabajador,
            "importe": base_cotizacion * (porcentajes.contingencias_comunes_trabajador / Decimal("100")),
        },
        "mei_empresa": {
            "porcentaje": porcentajes.mei_empresa,
            "importe": base_cotizacion * (porcentajes.mei_empresa / Decimal("100")),
        },
        "mei_trabajador": {
            "porcentaje": porcentajes.mei_trabajador,
            "importe": base_cotizacion * (porcentajes.mei_trabajador / Decimal("100")),
        },
        "desempleo_empresa": {
            "porcentaje": porcentajes.desempleo_empresa,
            "importe": base_cotizacion * (porcentajes.desempleo_empresa / Decimal("100")),
        },
        "desempleo_trabajador": {
            "porcentaje": porcentajes.desempleo_trabajador,
            "importe": base_cotizacion * (porcentajes.desempleo_trabajador / Decimal("100")),
        },
        "formacion_empresa": {
            "porcentaje": porcentajes.formacion_empresa,
            "importe": base_cotizacion * (porcentajes.formacion_empresa / Decimal("100")),
        },
        "formacion_trabajador": {
            "porcentaje": porcentajes.formacion_trabajador,
            "importe": base_cotizacion * (porcentajes.formacion_trabajador / Decimal("100")),
        },
        "at_ep_empresa": {
            "porcentaje": porcentajes.at_ep_empresa,
            "importe": base_cotizacion * (porcentajes.at_ep_empresa / Decimal("100")),
        },
        "fogasa_empresa": {
            "porcentaje": porcentajes.fogasa_empresa,
            "importe": base_cotizacion * (porcentajes.fogasa_empresa / Decimal("100")),
        },
    }

    porcentaje_ss_total = (
        porcentajes.contingencias_comunes_empresa
        + porcentajes.mei_empresa
        + porcentajes.desempleo_empresa
        + porcentajes.formacion_empresa
        + porcentajes.at_ep_empresa
        + porcentajes.fogasa_empresa
        + porcentajes.contingencias_comunes_trabajador
        + porcentajes.mei_trabajador
        + porcentajes.desempleo_trabajador
        + porcentajes.formacion_trabajador
    )

    neto_por_artista = costes["neto"]

    return JsonResponse(
        {
            "ok": True,
            "tramo": tramo.numero_tramo,
            "rango": f"{tramo.rango_minimo} - {tramo.rango_maximo}",
            "resumen": {
                "importe_bruto": f"{costes['importe_bruto']:.2f}",
                "base_imponible": f"{costes['base_imponible']:.2f}",
                "num_dias": f"{num_dias:.0f}",
                "iva_porcentaje": f"{costes['iva_porcentaje']:.2f}",
                "iva_importe": f"{costes['iva_importe']:.2f}",
                "total_con_iva": f"{costes['total_con_iva']:.2f}",
                "porcentaje_ss_total": f"{porcentaje_ss_total:.4f}",
                "porcentaje_irpf": f"{(porcentaje_irpf or Decimal('0')):.4f}",
                "porcentaje_honorarios": f"{costes['porcentaje_honorarios_aplicado']:.4f}",
                "presupuesto_nomina": f"{costes['presupuesto_nomina']:.2f}",
                "coste_ss_empresa": f"{costes['coste_empresa']:.2f}",
                "salario_bruto": f"{salario_bruto:.2f}",
                "base_diaria_estimada": f"{costes['base_diaria_estimada']:.2f}",
                "base_cotizacion_diaria": f"{costes['base_cotizacion_diaria']:.2f}",
                "base_cotizacion": f"{base_cotizacion:.2f}",
                "coste_ss_trabajador": f"{costes['coste_seguridad_social']:.2f}",
                "coste_ss_total": f"{costes['coste_ss_total']:.2f}",
                "base_irpf": f"{costes['base_irpf']:.2f}",
                "detalle_ss": {
                    key: {
                        "porcentaje": f"{value['porcentaje']:.4f}",
                        "importe": f"{value['importe']:.2f}",
                    }
                    for key, value in detalle_ss.items()
                },
                "neto_por_artista": f"{neto_por_artista:.2f}",
                "cantidad_artistas": f"{cantidad_artistas:.0f}",
                "neto_total": f"{costes['neto_total']:.2f}",
            },
            "costes": {
                "coste_empresa": f"{costes['coste_ss_total']:.2f}",
                "coste_gestion": f"{costes['coste_gestion']:.2f}",
                "coste_seguridad_social": f"{costes['coste_seguridad_social']:.2f}",
                "coste_irpf": f"{costes['coste_irpf']:.2f}",
            },
        }
    )


@login_required
def calcular_costes_desde_neto(request):
    """Calcula costes a partir del salario neto líquido (SAL.LIQUID)"""
    neto_liquido = request.GET.get("neto_liquido", "").strip()
    tipo_irpf = request.GET.get("tipo_irpf", "").strip()
    artista_id = request.GET.get("artista", "").strip()
    tipo_registro = request.GET.get("tipo_registro", "").strip()
    agrupacion_id = request.GET.get("agrupacion", "").strip()
    contexto_calculo = request.GET.get("contexto", "registro").strip()
    honorario_artista = None
    porcentaje_irpf = None

    if not neto_liquido:
        return JsonResponse({"ok": False, "error": "Debes indicar un salario neto."}, status=400)

    try:
        importe_neto_liquido = Decimal(neto_liquido)
    except InvalidOperation:
        return JsonResponse({"ok": False, "error": "El salario neto no tiene un formato válido."}, status=400)

    if importe_neto_liquido <= 0:
        return JsonResponse({"ok": False, "error": "El salario neto debe ser mayor que 0."}, status=400)

    # Obtener artista para coger su IRPF e honorario
    artista = None
    if artista_id:
        artista = Artist.objects.filter(pk=artista_id).first()
        if artista:
            # Usar IRPF del artista por defecto
            if not tipo_irpf and artista.irpf is not None:
                porcentaje_irpf = artista.irpf
            # Usar honorario del artista
            if artista.honorario is not None:
                honorario_artista = artista.honorario

    # Si se proporciona explícitamente IRPF, usar ese
    if tipo_irpf:
        try:
            porcentaje_irpf = Decimal(tipo_irpf)
        except InvalidOperation:
            return JsonResponse({"ok": False, "error": "El tipo de IRPF no tiene un formato válido."}, status=400)
        if porcentaje_irpf < 0:
            return JsonResponse({"ok": False, "error": "El tipo de IRPF no puede ser negativo."}, status=400)

    # Usar el tramo 1 por defecto para calcular desde neto
    # El tramo se determinaría por el salario_bruto resultante
    tramo = PriceBracket.objects.filter(numero_tramo=1, activo=True).first()
    if not tramo:
        return JsonResponse({"ok": False, "error": "No existe un tramo activo para calcular."}, status=404)

    costes = tramo.calculate_costs_from_net(
        importe_neto_liquido,
        irpf_percentage=porcentaje_irpf,
        honorarios_percentage=honorario_artista,
    )

    # Si el salario bruto está fuera del rango del tramo 1, buscar tramo correcto
    salario_bruto = costes["salario_bruto"]
    tramo_correcto = PriceBracket.get_bracket_for_amount(salario_bruto)
    if tramo_correcto and tramo_correcto.numero_tramo != 1:
        # Recalcular con el tramo correcto
        costes = tramo_correcto.calculate_costs_from_net(
            importe_neto_liquido,
            irpf_percentage=porcentaje_irpf,
            honorarios_percentage=honorario_artista,
        )
        tramo = tramo_correcto

    base_cotizacion = costes["base_cotizacion"]
    salario_bruto = costes["salario_bruto"]

    detalle_ss = {
        "contingencias_comunes_empresa": {
            "porcentaje": porcentajes.contingencias_comunes_empresa,
            "importe": base_cotizacion * (porcentajes.contingencias_comunes_empresa / Decimal("100")),
        },
        "contingencias_comunes_trabajador": {
            "porcentaje": porcentajes.contingencias_comunes_trabajador,
            "importe": base_cotizacion * (porcentajes.contingencias_comunes_trabajador / Decimal("100")),
        },
        "mei_empresa": {
            "porcentaje": porcentajes.mei_empresa,
            "importe": base_cotizacion * (porcentajes.mei_empresa / Decimal("100")),
        },
        "mei_trabajador": {
            "porcentaje": porcentajes.mei_trabajador,
            "importe": base_cotizacion * (porcentajes.mei_trabajador / Decimal("100")),
        },
        "desempleo_empresa": {
            "porcentaje": porcentajes.desempleo_empresa,
            "importe": base_cotizacion * (porcentajes.desempleo_empresa / Decimal("100")),
        },
        "desempleo_trabajador": {
            "porcentaje": porcentajes.desempleo_trabajador,
            "importe": base_cotizacion * (porcentajes.desempleo_trabajador / Decimal("100")),
        },
        "formacion_empresa": {
            "porcentaje": porcentajes.formacion_empresa,
            "importe": base_cotizacion * (porcentajes.formacion_empresa / Decimal("100")),
        },
        "formacion_trabajador": {
            "porcentaje": porcentajes.formacion_trabajador,
            "importe": base_cotizacion * (porcentajes.formacion_trabajador / Decimal("100")),
        },
        "at_ep_empresa": {
            "porcentaje": porcentajes.at_ep_empresa,
            "importe": base_cotizacion * (porcentajes.at_ep_empresa / Decimal("100")),
        },
        "fogasa_empresa": {
            "porcentaje": porcentajes.fogasa_empresa,
            "importe": base_cotizacion * (porcentajes.fogasa_empresa / Decimal("100")),
        },
    }

    porcentaje_ss_total = (
        porcentajes.contingencias_comunes_empresa
        + porcentajes.mei_empresa
        + porcentajes.desempleo_empresa
        + porcentajes.formacion_empresa
        + porcentajes.at_ep_empresa
        + porcentajes.fogasa_empresa
        + porcentajes.contingencias_comunes_trabajador
        + porcentajes.mei_trabajador
        + porcentajes.desempleo_trabajador
        + porcentajes.formacion_trabajador
    )

    cantidad_artistas = Decimal("1")
    if contexto_calculo == "agrupacion" and tipo_registro == ArtistRecord.RegistrationType.BAND and agrupacion_id:
        try:
            agrupacion = Grouping.objects.filter(pk=agrupacion_id).first()
            if agrupacion:
                total = agrupacion.artistas.count()
                if total > 0:
                    cantidad_artistas = Decimal(total)
        except Exception:
            cantidad_artistas = Decimal("1")

    cache_net = costes["cache_net"]
    importe_bruto = costes["importe_bruto"]
    importe_total_empresa = costes["importe_total_empresa"]

    iva_porcentaje = Decimal("21")
    iva_importe = (importe_total_empresa * iva_porcentaje) / Decimal("100")
    total_con_iva = importe_total_empresa + iva_importe

    return JsonResponse(
        {
            "ok": True,
            "tramo": tramo.numero_tramo,
            "rango": f"{tramo.rango_minimo} - {tramo.rango_maximo}",
            "resumen": {
                "neto_liquido": f"{importe_neto_liquido:.2f}",
                "importe_bruto": f"{importe_bruto:.2f}",
                "cache_neto": f"{cache_net:.2f}",
                "importe_total_empresa": f"{importe_total_empresa:.2f}",
                "iva_porcentaje": f"{iva_porcentaje:.2f}",
                "iva_importe": f"{iva_importe:.2f}",
                "total_con_iva": f"{total_con_iva:.2f}",
                "porcentaje_ss_total": f"{porcentaje_ss_total:.4f}",
                "porcentaje_irpf": f"{(porcentaje_irpf or Decimal('0')):.4f}",
                "porcentaje_honorarios": f"{costes['porcentaje_honorarios_aplicado']:.4f}",
                "presupuesto_nomina": f"{costes['presupuesto_nomina']:.2f}",
                "coste_ss_empresa": f"{costes['coste_empresa']:.2f}",
                "salario_bruto": f"{salario_bruto:.2f}",
                "base_cotizacion": f"{base_cotizacion:.2f}",
                "coste_ss_trabajador": f"{costes['coste_seguridad_social']:.2f}",
                "base_irpf": f"{costes['base_irpf']:.2f}",
                "detalle_ss": {
                    key: {
                        "porcentaje": f"{value['porcentaje']:.4f}",
                        "importe": f"{value['importe']:.2f}",
                    }
                    for key, value in detalle_ss.items()
                },
                "neto_por_artista": f"{costes['neto']:.2f}",
                "cantidad_artistas": f"{cantidad_artistas:.0f}",
                "neto_total": f"{(costes['neto'] * cantidad_artistas):.2f}",
            },
            "costes": {
                "coste_empresa": f"{costes['coste_ss_total']:.2f}",
                "coste_gestion": f"{costes['coste_gestion']:.2f}",
                "coste_seguridad_social": f"{costes['coste_seguridad_social']:.2f}",
                "coste_irpf": f"{costes['coste_irpf']:.2f}",
            },
        }
    )


@login_required
def calcular_costes_agrupacion(request):
    lineas_raw = request.GET.get("lineas", "").strip()
    fecha_alta_raw = request.GET.get("fecha_alta", "").strip()
    fecha_baja_raw = request.GET.get("fecha_baja", "").strip()
    if not lineas_raw:
        return JsonResponse({"ok": False, "error": "Añade al menos un artista con su caché."}, status=400)

    try:
        lineas = json.loads(lineas_raw)
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "No se pudieron interpretar las líneas enviadas."}, status=400)

    if not isinstance(lineas, list) or not lineas:
        return JsonResponse({"ok": False, "error": "Añade al menos una línea de artista."}, status=400)

    artist_ids = [str((item or {}).get("artista_id", "")).strip() for item in lineas if isinstance(item, dict)]
    artist_ids = [artist_id for artist_id in artist_ids if artist_id]
    if not artist_ids:
        return JsonResponse({"ok": False, "error": "Selecciona al menos un artista válido."}, status=400)

    artists_map = {str(artist.pk): artist for artist in Artist.objects.filter(pk__in=artist_ids)}
    if len(artists_map) != len(set(artist_ids)):
        return JsonResponse({"ok": False, "error": "Algunos artistas seleccionados no existen."}, status=400)

    items = []
    total_empresa = Decimal("0")
    total_gestion = Decimal("0")
    total_ss = Decimal("0")
    total_irpf = Decimal("0")
    total_neto = Decimal("0")
    total_bruto = Decimal("0")
    num_dias = calcular_num_dias(fecha_alta_raw, fecha_baja_raw)
    porcentajes = CostPercentageSettings.get_solo()
    porcentaje_empresa_total = (
        porcentajes.contingencias_comunes_empresa
        + porcentajes.mei_empresa
        + porcentajes.desempleo_empresa
        + porcentajes.formacion_empresa
        + porcentajes.at_ep_empresa
        + porcentajes.fogasa_empresa
    )

    for index, line in enumerate(lineas, start=1):
        if not isinstance(line, dict):
            return JsonResponse({"ok": False, "error": f"Línea {index}: formato inválido."}, status=400)

        artist_id = str(line.get("artista_id", "")).strip()
        cache_raw = str(line.get("cache_neto", "")).strip().replace(",", ".")
        if not artist_id:
            return JsonResponse({"ok": False, "error": f"Línea {index}: falta el artista."}, status=400)
        if not cache_raw:
            return JsonResponse({"ok": False, "error": f"Línea {index}: falta el caché neto."}, status=400)

        try:
            importe_cache_neto = Decimal(cache_raw)
        except InvalidOperation:
            return JsonResponse({"ok": False, "error": f"Línea {index}: caché neto inválido."}, status=400)
        if importe_cache_neto <= 0:
            return JsonResponse({"ok": False, "error": f"Línea {index}: el caché neto debe ser mayor que 0."}, status=400)

        artist = artists_map.get(artist_id)
        if not artist:
            return JsonResponse({"ok": False, "error": f"Línea {index}: artista no válido."}, status=400)

        honorario_artista = artist.honorario if artist.honorario is not None else None
        irpf_artista = artist.irpf if artist.irpf is not None else Decimal("0")

        tramo = PriceBracket.get_bracket_for_calculator(
            importe_cache_neto,
            num_days=num_dias,
            n_artistas=Decimal("1"),
            porcentaje_empresa_total=porcentaje_empresa_total,
        )
        if not tramo:
            return JsonResponse({"ok": False, "error": f"Línea {index}: no existe un tramo activo para ese cálculo."}, status=404)

        costes = tramo.calculate_costs(
            importe_cache_neto,
            irpf_percentage=irpf_artista,
            honorarios_percentage=honorario_artista,
            num_days=num_dias,
            n_artistas=Decimal("1"),
        )
        total_empresa += costes["coste_empresa"]
        total_gestion += costes["coste_gestion"]
        total_ss += costes["coste_seguridad_social"]
        total_irpf += costes["coste_irpf"]
        total_neto += costes["neto"]
        total_bruto += costes["importe_bruto"]

        items.append(
            {
                "id": artist.pk,
                "nombre": artist.nombre_completo,
                "cache_neto": f"{importe_cache_neto:.2f}",
                "importe_bruto": f"{costes['importe_bruto']:.2f}",
                "tramo": tramo.numero_tramo,
                "irpf": f"{irpf_artista:.2f}",
                "honorario": f"{costes['porcentaje_honorarios_aplicado']:.4f}",
                "coste_empresa": f"{costes['coste_empresa']:.2f}",
                "coste_gestion": f"{costes['coste_gestion']:.2f}",
                "coste_ss": f"{costes['coste_seguridad_social']:.2f}",
                "coste_irpf": f"{costes['coste_irpf']:.2f}",
                "neto": f"{costes['neto']:.2f}",
            }
        )

    return JsonResponse(
        {
            "ok": True,
            "items": items,
            "totales": {
                "cache_neto": f"{sum(Decimal(item['cache_neto']) for item in items):.2f}",
                "bruto": f"{total_bruto:.2f}",
                "empresa": f"{total_empresa:.2f}",
                "gestion": f"{total_gestion:.2f}",
                "ss": f"{total_ss:.2f}",
                "irpf": f"{total_irpf:.2f}",
                "neto": f"{total_neto:.2f}",
            },
        }
    )


@login_required
def agrupacion_artistas(request):
    agrupacion_id = request.GET.get("agrupacion", "").strip()
    if not agrupacion_id:
        return JsonResponse({"ok": False, "error": "Debes indicar una agrupación."}, status=400)

    grouping = Grouping.objects.filter(pk=agrupacion_id).prefetch_related("artistas").first()
    if not grouping:
        return JsonResponse({"ok": False, "error": "No se encontró la agrupación."}, status=404)

    artists = [
        {"id": str(artist.pk), "nombre": artist.nombre_completo}
        for artist in grouping.artistas.order_by("nombre_completo")
    ]
    return JsonResponse({"ok": True, "artistas": artists})


class ArtistListView(LoginRequiredMixin, ListView):
    model = Artist
    template_name = "artists/artist_list.html"
    context_object_name = "artists"

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .prefetch_related("agrupaciones")
            .annotate(total_registros=Count("registros"))
        )
        query = self.request.GET.get("q", "").strip()

        if query:
            queryset = queryset.filter(
                Q(nombre_completo__icontains=query)
                | Q(dni_nie__icontains=query)
                | Q(numero_seguridad_social__icontains=query)
                | Q(cuenta_bancaria__icontains=query)
                | Q(telefono__icontains=query)
                | Q(email__icontains=query)
                | Q(agrupaciones__nombre__icontains=query)
            )
            queryset = queryset.distinct()

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
    optional_columns = [
        "irpf",
        "honorario",
        "telefono",
        "email",
        "prl",
    ]
    form = ArtistCSVUploadForm(request.POST or None, request.FILES or None)
    context = {
        "form": form,
        "required_columns": required_columns,
        "optional_columns": optional_columns,
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
                    "irpf": normalized_row.get("irpf", "") or 15,
                    "honorario": normalized_row.get("honorario", "") or None,
                    "telefono": normalized_row.get("telefono", ""),
                    "email": normalized_row.get("email", ""),
                    "prl": normalized_row.get("prl", "").strip().lower() in {"1", "si", "sí", "true", "yes", "y"},
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


class GroupingRecordBatchCreateView(LoginRequiredMixin, FormView):
    template_name = "artists/grouping_record_form.html"
    form_class = GroupingRecordBatchForm
    success_url = reverse_lazy("artists:record-list")

    def get_initial(self):
        initial = super().get_initial()
        agrupacion_id = self.request.GET.get("agrupacion", "").strip()
        if agrupacion_id:
            grouping = Grouping.objects.filter(pk=agrupacion_id).prefetch_related("artistas").first()
            if grouping:
                initial["agrupacion"] = grouping.pk
                initial["lineas"] = json.dumps(
                    [
                        {
                            "artista_id": str(artist.pk),
                            "cache_neto": "",
                            "es_autonomo": False,
                            "solicitud_a1": False,
                            "destino_a1": "",
                        }
                        for artist in grouping.artistas.order_by("nombre_completo")
                    ]
                )
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["artists_catalog"] = Artist.objects.order_by("nombre_completo")
        context["form_mode"] = "create"
        return context

    def form_valid(self, form):
        cleaned = form.cleaned_data
        lineas = cleaned.get("lineas_normalizadas", [])

        with transaction.atomic():
            created = 0
            for item in lineas:
                artist = item["artista"]
                record = ArtistRecord(
                    artista=artist,
                    agrupacion=cleaned["agrupacion"],
                    tipo_registro=ArtistRecord.RegistrationType.BAND,
                    es_autonomo=item["es_autonomo"],
                    tipo_irpf=artist.irpf,
                    fecha_alta=cleaned["fecha_alta"],
                    fecha_baja=cleaned.get("fecha_baja"),
                    solicitud_a1=item["solicitud_a1"],
                    destino_a1=item["destino_a1"],
                    proceso_cancelado=cleaned["proceso_cancelado"],
                    cache_neto=item["cache_neto"],
                    estado_pago=cleaned["estado_pago"],
                    observaciones=cleaned.get("observaciones", ""),
                )
                record.calculate_and_update_costs()
                record.save()
                created += 1

        messages.success(self.request, f"Se han creado {created} registros para la agrupación seleccionada.")
        return super().form_valid(form)


class GroupingRecordListView(LoginRequiredMixin, ListView):
    model = Grouping
    template_name = "artists/grouping_record_list.html"
    context_object_name = "groupings"

    def get_queryset(self):
        return (
            Grouping.objects
            .prefetch_related("artistas")
            .annotate(
                total_artistas=Count("artistas", distinct=True),
                total_registros=Count(
                    "registros_artistas",
                    filter=~Q(registros_artistas__estado_pago=ArtistRecord.PaymentStatus.PAID),
                    distinct=True,
                ),
                ultima_alta=Max("registros_artistas__fecha_alta"),
            )
            .order_by("nombre")
        )


class GroupingRecordBatchUpdateView(LoginRequiredMixin, FormView):
    template_name = "artists/grouping_record_form.html"
    form_class = GroupingRecordBatchForm
    success_url = reverse_lazy("artists:record-grouping-list")

    def get_grouping(self):
        return Grouping.objects.prefetch_related("artistas").get(pk=self.kwargs["pk"])

    def get_editable_records(self):
        records = (
            ArtistRecord.objects
            .filter(agrupacion_id=self.kwargs["pk"])
            .exclude(estado_pago=ArtistRecord.PaymentStatus.PAID)
            .select_related("artista", "agrupacion")
            .order_by("artista_id", "-fecha_alta", "-creado_en")
        )
        editable = {}
        for record in records:
            editable.setdefault(record.artista_id, record)
        return editable

    def get_initial(self):
        initial = super().get_initial()
        grouping = self.get_grouping()
        editable_map = self.get_editable_records()

        initial["agrupacion"] = grouping.pk
        if editable_map:
            latest_record = max(editable_map.values(), key=lambda record: (record.fecha_alta, record.creado_en))
            initial.update(
                {
                    "fecha_alta": latest_record.fecha_alta,
                    "fecha_baja": latest_record.fecha_baja,
                    "proceso_cancelado": latest_record.proceso_cancelado,
                    "estado_pago": latest_record.estado_pago,
                    "observaciones": latest_record.observaciones,
                }
            )
            lineas = [
                {
                    "artista_id": str(record.artista_id),
                    "cache_neto": f"{record.cache_neto:.2f}",
                    "es_autonomo": record.es_autonomo,
                    "solicitud_a1": record.solicitud_a1,
                    "destino_a1": record.destino_a1 or "",
                }
                for record in sorted(editable_map.values(), key=lambda record: record.artista.nombre_completo)
            ]
        else:
            lineas = [
                {
                    "artista_id": str(artist.pk),
                    "cache_neto": "",
                    "es_autonomo": False,
                    "solicitud_a1": False,
                    "destino_a1": "",
                }
                for artist in grouping.artistas.order_by("nombre_completo")
            ]
        initial["lineas"] = json.dumps(lineas)
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["artists_catalog"] = Artist.objects.order_by("nombre_completo")
        context["form_mode"] = "edit"
        context["grouping"] = self.get_grouping()
        return context

    def form_valid(self, form):
        cleaned = form.cleaned_data
        lineas = cleaned.get("lineas_normalizadas", [])
        editable_map = self.get_editable_records()
        selected_ids = {item["artista"].pk for item in lineas}

        with transaction.atomic():
            updated = 0
            created = 0

            for item in lineas:
                artist = item["artista"]
                record = editable_map.get(artist.pk)
                if record is None:
                    record = ArtistRecord(
                        artista=artist,
                        agrupacion=cleaned["agrupacion"],
                        tipo_registro=ArtistRecord.RegistrationType.BAND,
                    )
                    created += 1
                else:
                    updated += 1

                record.es_autonomo = item["es_autonomo"]
                record.tipo_irpf = artist.irpf
                record.fecha_alta = cleaned["fecha_alta"]
                record.fecha_baja = cleaned.get("fecha_baja")
                record.solicitud_a1 = item["solicitud_a1"]
                record.destino_a1 = item["destino_a1"]
                record.proceso_cancelado = cleaned["proceso_cancelado"]
                record.cache_neto = item["cache_neto"]
                record.estado_pago = cleaned["estado_pago"]
                record.observaciones = cleaned.get("observaciones", "")
                record.calculate_and_update_costs()
                record.save()

            for artist_id, record in editable_map.items():
                if artist_id not in selected_ids:
                    record.delete()

        messages.success(
            self.request,
            f"Agrupación actualizada: {updated} registros actualizados y {created} creados.",
        )
        return super().form_valid(form)


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
    success_url = reverse_lazy("artists:grouping-list")

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


class GroupingListView(LoginRequiredMixin, ListView):
    model = Grouping
    template_name = "artists/grouping_list.html"
    context_object_name = "groupings"

    def get_queryset(self):
        return (
            Grouping.objects
            .prefetch_related("artistas")
            .annotate(total_artistas=Count("artistas"))
            .order_by("nombre")
        )


class GroupingUpdateView(LoginRequiredMixin, UpdateView):
    model = Grouping
    form_class = GroupingForm
    template_name = "artists/grouping_form.html"
    success_url = reverse_lazy("artists:grouping-list")


class CalculatorView(LoginRequiredMixin, TemplateView):
    template_name = "artists/calculator.html"
