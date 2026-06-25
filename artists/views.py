import csv
import io
import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, F, Max, Prefetch, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DeleteView, FormView, ListView, TemplateView, UpdateView

from .forms import ArtistCSVUploadForm, ArtistForm, ArtistRecordForm, GroupingForm, GroupingRecordBatchForm
from .models import Artist, ArtistRecord, CostPercentageSettings, Grouping, GroupingRecordBatch, PriceBracket


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
    """Calcula costes a partir de un neto total objetivo, invirtiendo el cálculo de caché neto."""
    neto_total_raw = request.GET.get("neto_total", "").strip()
    neto_liquido = request.GET.get("neto_liquido", "").strip()
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
    porcentaje_irpf = None
    importe_neto_objetivo = None

    porcentajes = CostPercentageSettings.get_solo()
    cantidad_artistas = Decimal("1")

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

    neto_input = neto_total_raw or neto_liquido
    if not neto_input:
        return JsonResponse({"ok": False, "error": "Debes indicar un neto total objetivo."}, status=400)

    try:
        importe_neto_objetivo = Decimal(neto_input)
    except InvalidOperation:
        return JsonResponse({"ok": False, "error": "El neto total no tiene un formato válido."}, status=400)

    if importe_neto_objetivo <= 0:
        return JsonResponse({"ok": False, "error": "El neto total debe ser mayor que 0."}, status=400)

    if artista_id:
        artista = Artist.objects.filter(pk=artista_id).first()
        if artista and artista.honorario is not None:
            honorario_artista = artista.honorario

    if tipo_irpf:
        try:
            porcentaje_irpf = Decimal(tipo_irpf)
        except InvalidOperation:
            return JsonResponse({"ok": False, "error": "El tipo de IRPF no tiene un formato válido."}, status=400)
        if porcentaje_irpf < 0:
            return JsonResponse({"ok": False, "error": "El tipo de IRPF no puede ser negativo."}, status=400)

    porcentaje_empresa_total = (
        porcentajes.contingencias_comunes_empresa
        + porcentajes.mei_empresa
        + porcentajes.desempleo_empresa
        + porcentajes.formacion_empresa
        + porcentajes.at_ep_empresa
        + porcentajes.fogasa_empresa
    )

    def _resolver_costes(cache_neto_valor):
        tramo_actual = PriceBracket.get_bracket_for_calculator(
            cache_neto_valor,
            num_days=num_dias,
            n_artistas=cantidad_artistas,
            porcentaje_empresa_total=porcentaje_empresa_total,
        )
        if not tramo_actual:
            return None, None

        costes_actuales = tramo_actual.calculate_costs(
            cache_neto_valor,
            irpf_percentage=porcentaje_irpf,
            honorarios_percentage=honorario_artista,
            num_days=num_dias,
            n_artistas=cantidad_artistas,
        )
        return tramo_actual, costes_actuales

    minimo_cache = Decimal("0.01")
    tramo_min, costes_min = _resolver_costes(minimo_cache)
    if not tramo_min or not costes_min:
        return JsonResponse({"ok": False, "error": "No existe un tramo activo para ese cálculo."}, status=404)

    if costes_min["neto_total"] >= importe_neto_objetivo:
        tramo = tramo_min
        costes = costes_min
    else:
        cache_bajo = minimo_cache
        cache_alto = max(importe_neto_objetivo * Decimal("2"), Decimal("10"))
        tramo = None
        costes = None

        for _ in range(30):
            tramo_alto, costes_alto = _resolver_costes(cache_alto)
            if not tramo_alto or not costes_alto:
                return JsonResponse({"ok": False, "error": "No existe un tramo activo para ese cálculo."}, status=404)

            if costes_alto["neto_total"] >= importe_neto_objetivo:
                tramo = tramo_alto
                costes = costes_alto
                break

            cache_alto *= Decimal("2")

        if not tramo or not costes:
            return JsonResponse(
                {"ok": False, "error": "No se pudo encontrar un caché neto para el neto total indicado."},
                status=400,
            )

        for _ in range(70):
            cache_medio = (cache_bajo + cache_alto) / Decimal("2")
            tramo_medio, costes_medio = _resolver_costes(cache_medio)
            if not tramo_medio or not costes_medio:
                continue

            if costes_medio["neto_total"] < importe_neto_objetivo:
                cache_bajo = cache_medio
            else:
                cache_alto = cache_medio
                tramo = tramo_medio
                costes = costes_medio

            if (cache_alto - cache_bajo) < Decimal("0.0001"):
                break

    if not tramo or not costes:
        return JsonResponse(
            {"ok": False, "error": "No se pudo resolver el cálculo inverso para ese neto total."},
            status=400,
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
                "neto_objetivo_total": f"{importe_neto_objetivo:.2f}",
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
            .exclude(estado_pago=ArtistRecord.PaymentStatus.ABONADO)
        )
        query = self.request.GET.get("q", "").strip()
        payment_status = self.request.GET.get("estado_pago", "").strip()
        seguridad_social_status = self.request.GET.get("estado_seguridad_social", "").strip()
        facturacion_status = self.request.GET.get("estado_facturacion", "").strip()
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
        if payment_status and payment_status != ArtistRecord.PaymentStatus.ABONADO:
            queryset = queryset.filter(estado_pago=payment_status)
        if seguridad_social_status:
            queryset = queryset.filter(estado_seguridad_social=seguridad_social_status)
        if facturacion_status:
            queryset = queryset.filter(estado_facturacion=facturacion_status)
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

        return queryset.order_by("-fecha_alta", "-creado_en")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["groupings"] = Grouping.objects.filter(activo=True).order_by("nombre")
        context["artists_for_filter"] = Artist.objects.order_by("nombre_completo")
        context["payment_status_choices"] = [
            choice
            for choice in ArtistRecord.PaymentStatus.choices
            if choice[0] != ArtistRecord.PaymentStatus.ABONADO
        ]
        context["seguridad_social_status_choices"] = ArtistRecord.SeguridadSocialStatus.choices
        context["facturacion_status_choices"] = ArtistRecord.FacturacionStatus.choices
        context["registration_type_choices"] = ArtistRecord.RegistrationType.choices
        context["filter_values"] = {
            "q": self.request.GET.get("q", ""),
            "estado_pago": self.request.GET.get("estado_pago", ""),
            "estado_seguridad_social": self.request.GET.get("estado_seguridad_social", ""),
            "estado_facturacion": self.request.GET.get("estado_facturacion", ""),
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
        context["artists_payload"] = [
            {
                "id": artist.pk,
                "irpf": str(artist.irpf),
                "honorario": "" if artist.honorario is None else str(artist.honorario),
            }
            for artist in Artist.objects.order_by("nombre_completo")
        ]
        return context


class ArtistRecordUpdateView(LoginRequiredMixin, UpdateView):
    model = ArtistRecord
    form_class = ArtistRecordForm
    template_name = "artists/artist_record_form.html"
    success_url = reverse_lazy("artists:record-list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["ruta_actual"] = self.request.get_full_path()
        context["artists_payload"] = [
            {
                "id": artist.pk,
                "irpf": str(artist.irpf),
                "honorario": "" if artist.honorario is None else str(artist.honorario),
            }
            for artist in Artist.objects.order_by("nombre_completo")
        ]
        return context


class GroupingRecordBatchCreateView(LoginRequiredMixin, FormView):
    template_name = "artists/grouping_record_form.html"
    form_class = GroupingRecordBatchForm
    success_url = reverse_lazy("artists:record-list")

    @staticmethod
    def _sum_lineas_cache(lineas):
        total = Decimal("0")
        for item in lineas or []:
            if not isinstance(item, dict):
                continue
            try:
                total += Decimal(str(item.get("cache_neto", "0")).replace(",", "."))
            except (InvalidOperation, TypeError):
                continue
        return total

    def _get_standby_batch(self):
        batch_id = (self.request.POST.get("batch_id") or self.request.GET.get("batch") or "").strip()
        if not batch_id:
            return None
        return GroupingRecordBatch.objects.filter(
            pk=batch_id,
            estado=GroupingRecordBatch.BatchStatus.STANDBY,
        ).select_related("agrupacion").first()

    def get_initial(self):
        initial = super().get_initial()
        standby_batch = self._get_standby_batch()
        if standby_batch:
            initial.update(
                {
                    "agrupacion": standby_batch.agrupacion_id,
                    "base_imponible": standby_batch.base_imponible or self._sum_lineas_cache(standby_batch.lineas),
                    "honorarios": standby_batch.honorarios,
                    "gastos": json.dumps(standby_batch.gastos or [], ensure_ascii=False),
                    "lineas": json.dumps(standby_batch.lineas or []),
                    "fecha_alta": standby_batch.fecha_alta,
                    "fecha_baja": standby_batch.fecha_baja,
                    "proceso_cancelado": standby_batch.proceso_cancelado,
                    "estado_pago": standby_batch.estado_pago,
                    "observaciones": standby_batch.observaciones,
                }
            )
            return initial

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
        context["standby_batch"] = self._get_standby_batch()
        return context

    @staticmethod
    def _create_artist_records(cleaned, lineas, batch=None):
        created = 0
        for item in lineas:
            artist = item["artista"]
            record = ArtistRecord(
                artista=artist,
                agrupacion=cleaned["agrupacion"],
                lote_agrupacion=batch,
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
            record.full_clean()
            record.calculate_and_update_costs()
            record.save()
            created += 1
        return created

    def form_valid(self, form):
        cleaned = form.cleaned_data
        lineas = cleaned.get("lineas_normalizadas", [])
        submit_action = self.request.POST.get("submit_action", "generate")
        standby_batch = self._get_standby_batch()

        serialized_lineas = [
            {
                "artista_id": item["artista"].pk,
                "cache_neto": str(item["cache_neto"]),
                "es_autonomo": item["es_autonomo"],
                "solicitud_a1": item["solicitud_a1"],
                "destino_a1": item["destino_a1"],
            }
            for item in lineas
        ]
        serialized_gastos = [
            {
                "concepto": item["concepto"],
                "importe": str(item["importe"]),
            }
            for item in cleaned.get("gastos_normalizados", [])
        ]

        if submit_action == "standby":
            with transaction.atomic():
                if standby_batch:
                    standby_batch.agrupacion = cleaned["agrupacion"]
                    standby_batch.base_imponible = cleaned["base_imponible"]
                    standby_batch.honorarios = cleaned.get("honorarios") or Decimal("0")
                    standby_batch.gastos = serialized_gastos
                    standby_batch.lineas = serialized_lineas
                    standby_batch.fecha_alta = cleaned["fecha_alta"]
                    standby_batch.fecha_baja = cleaned.get("fecha_baja")
                    standby_batch.proceso_cancelado = cleaned["proceso_cancelado"]
                    standby_batch.estado_pago = cleaned["estado_pago"]
                    standby_batch.observaciones = cleaned.get("observaciones", "")
                    standby_batch.save()
                else:
                    GroupingRecordBatch.objects.create(
                        agrupacion=cleaned["agrupacion"],
                        base_imponible=cleaned["base_imponible"],
                        honorarios=cleaned.get("honorarios") or Decimal("0"),
                        gastos=serialized_gastos,
                        lineas=serialized_lineas,
                        fecha_alta=cleaned["fecha_alta"],
                        fecha_baja=cleaned.get("fecha_baja"),
                        proceso_cancelado=cleaned["proceso_cancelado"],
                        estado_pago=cleaned["estado_pago"],
                        observaciones=cleaned.get("observaciones", ""),
                        estado=GroupingRecordBatch.BatchStatus.STANDBY,
                    )

            if standby_batch:
                messages.success(self.request, "Stand By actualizado correctamente.")
            else:
                messages.success(self.request, "Registro guardado en Stand By. Podras pasarlo a registros cuando quieras.")
            return redirect("artists:record-grouping-list")

        try:
            with transaction.atomic():
                batch_for_records = standby_batch
                if batch_for_records is None:
                    batch_for_records = GroupingRecordBatch.objects.create(
                        agrupacion=cleaned["agrupacion"],
                        base_imponible=cleaned["base_imponible"],
                        honorarios=cleaned.get("honorarios") or Decimal("0"),
                        gastos=serialized_gastos,
                        lineas=serialized_lineas,
                        fecha_alta=cleaned["fecha_alta"],
                        fecha_baja=cleaned.get("fecha_baja"),
                        proceso_cancelado=cleaned["proceso_cancelado"],
                        estado_pago=cleaned["estado_pago"],
                        observaciones=cleaned.get("observaciones", ""),
                        estado=GroupingRecordBatch.BatchStatus.PROCESSED,
                        generado_en=timezone.now(),
                    )

                created = self._create_artist_records(cleaned, lineas, batch=batch_for_records)

                if standby_batch:
                    standby_batch.agrupacion = cleaned["agrupacion"]
                    standby_batch.base_imponible = cleaned["base_imponible"]
                    standby_batch.honorarios = cleaned.get("honorarios") or Decimal("0")
                    standby_batch.gastos = serialized_gastos
                    standby_batch.lineas = serialized_lineas
                    standby_batch.fecha_alta = cleaned["fecha_alta"]
                    standby_batch.fecha_baja = cleaned.get("fecha_baja")
                    standby_batch.proceso_cancelado = cleaned["proceso_cancelado"]
                    standby_batch.estado_pago = cleaned["estado_pago"]
                    standby_batch.observaciones = cleaned.get("observaciones", "")
                    standby_batch.estado = GroupingRecordBatch.BatchStatus.PROCESSED
                    standby_batch.generado_en = timezone.now()
                    standby_batch.save()
        except ValidationError as exc:
            if hasattr(exc, "error_dict"):
                for field_name, errors in exc.error_dict.items():
                    for error in errors:
                        target_field = field_name if field_name in form.fields else None
                        form.add_error(target_field, error)
            else:
                form.add_error(None, "; ".join(exc.messages))
            return self.form_invalid(form)

        messages.success(self.request, f"Se han creado {created} registros para la agrupación seleccionada.")
        return super().form_valid(form)


class GroupingRecordBatchProcessStandbyView(LoginRequiredMixin, View):
    def post(self, request, pk):
        batch = get_object_or_404(
            GroupingRecordBatch.objects.select_related("agrupacion"),
            pk=pk,
            estado=GroupingRecordBatch.BatchStatus.STANDBY,
        )

        lineas_raw = batch.lineas if isinstance(batch.lineas, list) else []
        if not lineas_raw:
            messages.error(request, "El registro en Stand By no contiene lineas para generar registros.")
            return redirect("artists:record-grouping-list")

        if batch.base_disponible_para_artistas is not None and batch.total_cache_lineas > batch.base_disponible_para_artistas:
            messages.error(
                request,
                "No se puede procesar el Stand By porque la suma de los caches supera la base disponible.",
            )
            return redirect("artists:record-grouping-list")

        artist_ids = [str((item or {}).get("artista_id", "")).strip() for item in lineas_raw if isinstance(item, dict)]
        artists_map = {str(artist.pk): artist for artist in Artist.objects.filter(pk__in=artist_ids)}

        if len(artists_map) != len(set([artist_id for artist_id in artist_ids if artist_id])):
            messages.error(
                request,
                "No se pudo procesar el Stand By porque hay artistas eliminados o no validos.",
            )
            return redirect("artists:record-grouping-list")

        lineas_normalizadas = []
        for item in lineas_raw:
            artist_id = str((item or {}).get("artista_id", "")).strip()
            if not artist_id:
                continue

            try:
                cache_neto = Decimal(str((item or {}).get("cache_neto", "0")).replace(",", "."))
            except (InvalidOperation, TypeError):
                messages.error(request, "No se pudo procesar el Stand By porque algun caché neto no es valido.")
                return redirect("artists:record-grouping-list")

            if cache_neto <= 0:
                messages.error(request, "No se pudo procesar el Stand By porque hay lineas con caché neto vacio.")
                return redirect("artists:record-grouping-list")

            lineas_normalizadas.append(
                {
                    "artista": artists_map[artist_id],
                    "cache_neto": cache_neto,
                    "es_autonomo": bool((item or {}).get("es_autonomo", False)),
                    "solicitud_a1": bool((item or {}).get("solicitud_a1", False)),
                    "destino_a1": str((item or {}).get("destino_a1", "")).strip(),
                }
            )

        cleaned = {
            "agrupacion": batch.agrupacion,
            "fecha_alta": batch.fecha_alta,
            "fecha_baja": batch.fecha_baja,
            "proceso_cancelado": batch.proceso_cancelado,
            "estado_pago": batch.estado_pago,
            "observaciones": batch.observaciones,
        }

        try:
            with transaction.atomic():
                created = GroupingRecordBatchCreateView._create_artist_records(cleaned, lineas_normalizadas, batch=batch)
                batch.estado = GroupingRecordBatch.BatchStatus.PROCESSED
                batch.generado_en = timezone.now()
                batch.save(update_fields=["estado", "generado_en", "actualizado_en"])
        except ValidationError as exc:
            messages.error(
                request,
                "No se pudo procesar el Stand By por solape de fechas o registro abierto. "
                + "; ".join(exc.messages),
            )
            return redirect("artists:record-grouping-list")

        messages.success(request, f"Stand By procesado correctamente. Se han creado {created} registros.")
        return redirect("artists:record-grouping-list")


class GroupingRecordBatchDeleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        batch = get_object_or_404(GroupingRecordBatch, pk=pk)
        batch.delete()
        messages.success(request, "Registro de agrupación eliminado correctamente.")
        return redirect("artists:record-grouping-list")


class GroupingRecordListView(LoginRequiredMixin, ListView):
    model = GroupingRecordBatch
    template_name = "artists/grouping_record_list.html"
    context_object_name = "batch_records"

    def get_queryset(self):
        return (
            GroupingRecordBatch.objects
            .select_related("agrupacion")
            .order_by("-fecha_alta", "-creado_en")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        batches = context.get("batch_records")

        artist_ids = set()
        for batch in batches:
            lineas = batch.lineas if isinstance(batch.lineas, list) else []
            batch.total_lineas = len(lineas)
            for item in lineas:
                if not isinstance(item, dict):
                    continue
                artist_id = str(item.get("artista_id", "")).strip()
                if artist_id:
                    artist_ids.add(artist_id)

        artists_map = {str(artist.pk): artist for artist in Artist.objects.filter(pk__in=artist_ids)}

        for batch in batches:
            lineas = batch.lineas if isinstance(batch.lineas, list) else []
            artist_names = []
            for item in lineas:
                if not isinstance(item, dict):
                    continue
                artist_id = str(item.get("artista_id", "")).strip()
                artist = artists_map.get(artist_id)
                if artist:
                    artist_names.append(artist.nombre_completo)
            batch.artist_names = artist_names

        return context


class GroupingRecordBatchDetailView(LoginRequiredMixin, TemplateView):
    template_name = "artists/grouping_record_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        batch = get_object_or_404(
            GroupingRecordBatch.objects.select_related("agrupacion"),
            pk=self.kwargs["pk"],
        )

        lineas = batch.lineas if isinstance(batch.lineas, list) else []
        artist_ids = [
            str(item.get("artista_id", "")).strip()
            for item in lineas
            if isinstance(item, dict)
        ]
        artists_map = {str(artist.pk): artist for artist in Artist.objects.filter(pk__in=artist_ids)}

        lineas_detalle = []
        for item in lineas:
            if not isinstance(item, dict):
                continue
            artist_id = str(item.get("artista_id", "")).strip()
            artist = artists_map.get(artist_id)
            lineas_detalle.append(
                {
                    "artista_nombre": artist.nombre_completo if artist else f"Artista #{artist_id}",
                    "cache_neto": item.get("cache_neto", ""),
                    "es_autonomo": bool(item.get("es_autonomo", False)),
                    "solicitud_a1": bool(item.get("solicitud_a1", False)),
                    "destino_a1": (item.get("destino_a1", "") or "").strip(),
                }
            )

        context["batch"] = batch
        context["lineas_detalle"] = lineas_detalle
        return context


class GroupingRecordBatchUpdateView(LoginRequiredMixin, FormView):
    template_name = "artists/grouping_record_form.html"
    form_class = GroupingRecordBatchForm
    success_url = reverse_lazy("artists:record-grouping-list")

    def get_grouping(self):
        return Grouping.objects.prefetch_related("artistas").get(pk=self.kwargs["pk"])

    def get_latest_records(self):
        records = (
            ArtistRecord.objects
            .filter(agrupacion_id=self.kwargs["pk"])
            .exclude(estado_pago=ArtistRecord.PaymentStatus.ABONADO)
            .select_related("artista", "agrupacion")
            .order_by("artista_id", "-fecha_alta", "-creado_en")
        )
        latest = {}
        for record in records:
            latest.setdefault(record.artista_id, record)
        return latest

    def get_initial(self):
        initial = super().get_initial()
        grouping = self.get_grouping()
        latest_map = self.get_latest_records()

        initial["agrupacion"] = grouping.pk
        if latest_map:
            latest_record = max(latest_map.values(), key=lambda record: (record.fecha_alta, record.creado_en))
            total_cache = sum((record.cache_neto for record in latest_map.values()), Decimal("0"))
            initial.update(
                {
                    "base_imponible": total_cache,
                    "honorarios": Decimal("0"),
                    "gastos": "[]",
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
                for record in sorted(latest_map.values(), key=lambda record: record.artista.nombre_completo)
            ]
        else:
            initial.update(
                {
                    "honorarios": Decimal("0"),
                    "gastos": "[]",
                }
            )
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

        serialized_lineas = [
            {
                "artista_id": item["artista"].pk,
                "cache_neto": str(item["cache_neto"]),
                "es_autonomo": item["es_autonomo"],
                "solicitud_a1": item["solicitud_a1"],
                "destino_a1": item["destino_a1"],
            }
            for item in lineas
        ]
        serialized_gastos = [
            {
                "concepto": item["concepto"],
                "importe": str(item["importe"]),
            }
            for item in cleaned.get("gastos_normalizados", [])
        ]

        try:
            with transaction.atomic():
                GroupingRecordBatch.objects.create(
                    agrupacion=cleaned["agrupacion"],
                    base_imponible=cleaned["base_imponible"],
                    honorarios=cleaned.get("honorarios") or Decimal("0"),
                    gastos=serialized_gastos,
                    lineas=serialized_lineas,
                    fecha_alta=cleaned["fecha_alta"],
                    fecha_baja=cleaned.get("fecha_baja"),
                    proceso_cancelado=cleaned["proceso_cancelado"],
                    estado_pago=cleaned["estado_pago"],
                    observaciones=cleaned.get("observaciones", ""),
                    estado=GroupingRecordBatch.BatchStatus.PROCESSED,
                    generado_en=timezone.now(),
                )
                created = GroupingRecordBatchCreateView._create_artist_records(cleaned, lineas)
        except ValidationError as exc:
            if hasattr(exc, "error_dict"):
                for field_name, errors in exc.error_dict.items():
                    for error in errors:
                        target_field = field_name if field_name in form.fields else None
                        form.add_error(target_field, error)
            else:
                form.add_error(None, "; ".join(exc.messages))
            return self.form_invalid(form)

        messages.success(
            self.request,
            f"Nueva alta registrada para la agrupación: {created} registros creados.",
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

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        batch = self.object.lote_agrupacion
        response = super().delete(request, *args, **kwargs)

        if batch and not batch.registros_creados.exists():
            batch.delete()

        return response


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
