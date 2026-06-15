from decimal import Decimal

from django.db import models


class Grouping(models.Model):
    nombre = models.CharField(max_length=200, unique=True)
    descripcion = models.TextField(blank=True)
    activo = models.BooleanField(default=True)
    artistas = models.ManyToManyField("Artist", blank=True, related_name="agrupaciones")
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "agrupaciones"
        verbose_name = "Agrupación"
        verbose_name_plural = "Agrupaciones"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class PriceBracket(models.Model):
    """Tramos de precios para calcular costos según el caché neto"""
    numero_tramo = models.PositiveIntegerField(unique=True, help_text="Número de tramo (1-4)")
    rango_minimo = models.DecimalField(max_digits=10, decimal_places=2, help_text="Rango mínimo")
    rango_maximo = models.DecimalField(max_digits=10, decimal_places=2, help_text="Rango máximo")
    importe_base = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Base para cálculo (dejar vacío para tramo 1)"
    )
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tramos_precios"
        verbose_name = "Tramo de Precios"
        verbose_name_plural = "Tramos de Precios"
        ordering = ["numero_tramo"]

    def __str__(self):
        return f"Tramo {self.numero_tramo} ({self.rango_minimo} - {self.rango_maximo})"

    @classmethod
    def get_bracket_for_amount(cls, amount):
        """Obtiene el tramo correspondiente según el monto"""
        return cls.objects.filter(
            activo=True,
            rango_minimo__lte=amount,
            rango_maximo__gte=amount
        ).first()

    def calculate_costs(self, cache_net, irpf_percentage=None, honorarios_percentage=None):
        """
        Back-calculation desde Base Factura (cache_net) hasta Neto Líquido del artista.
        Régimen especial de artistas por día de la Seguridad Social.

        Paso 1: Comisión de gestión sobre Base Factura.
        Paso 2: Presupuesto de nómina disponible = Base Factura - Comisión.
        Paso 3: Retribución bruta estimada = Presupuesto / (1 + % empresa total).
        Paso 4: Base de cotización según tramo (= bruto en tramo 1, fija en tramos 2-4).
        Paso 5: SS empresa y Salario Bruto Real Final.
        Paso 6: SS trabajador, Base IRPF, Retención IRPF y Neto Líquido.
        """
        porcentajes = CostPercentageSettings.get_solo()

        porcentaje_honorarios_aplicado = (
            honorarios_percentage if honorarios_percentage is not None
            else porcentajes.porcentaje_honorarios
        )

        # --- Fuente 1: Porcentajes de cotización (CostPercentageSettings) ---
        porcentaje_empresa_total = (
            porcentajes.contingencias_comunes_empresa
            + porcentajes.mei_empresa
            + porcentajes.desempleo_empresa
            + porcentajes.formacion_empresa
            + porcentajes.at_ep_empresa
            + porcentajes.fogasa_empresa
        )
        porcentaje_trabajador_total = (
            porcentajes.contingencias_comunes_trabajador
            + porcentajes.mei_trabajador
            + porcentajes.desempleo_trabajador
            + porcentajes.formacion_trabajador
        )

        # Paso 1: Comisión de gestión
        coste_gestion = cache_net * (porcentaje_honorarios_aplicado / Decimal("100"))

        # Paso 2: Presupuesto de nómina disponible
        presupuesto_nomina = cache_net - coste_gestion

        # Paso 3: Retribución bruta estimada (para ubicar el tramo correcto)
        factor_empresa = Decimal("1") + porcentaje_empresa_total / Decimal("100")
        bruto_estimado = presupuesto_nomina / factor_empresa

        # --- Fuente 2: Tabla de Tramos (self / PriceBracket) ---
        # Pasos 4 y 5: Base de cotización y Salario Bruto Real Final
        if self.numero_tramo == 1:
            # Tramo 1: la base de cotización es la propia retribución bruta estimada
            base_cotizacion = bruto_estimado
            salario_bruto = bruto_estimado
        else:
            # Tramos 2-4: base de cotización fija según tabla
            base_cotizacion = self.importe_base or bruto_estimado
            coste_ss_empresa = base_cotizacion * (porcentaje_empresa_total / Decimal("100"))
            salario_bruto = presupuesto_nomina - coste_ss_empresa

        coste_empresa = base_cotizacion * (porcentaje_empresa_total / Decimal("100"))

        # Paso 6: Deducciones del trabajador, IRPF y Neto Líquido
        coste_seguridad_social = base_cotizacion * (porcentaje_trabajador_total / Decimal("100"))

        porcentaje_irpf_aplicado = irpf_percentage if irpf_percentage is not None else Decimal("0")
        base_irpf = salario_bruto - coste_seguridad_social
        if base_irpf < 0:
            base_irpf = Decimal("0")

        coste_irpf = base_irpf * (porcentaje_irpf_aplicado / Decimal("100"))

        neto = salario_bruto - coste_seguridad_social - coste_irpf
        if neto < 0:
            neto = Decimal("0")

        return {
            "coste_gestion": coste_gestion,
            "presupuesto_nomina": presupuesto_nomina,
            "bruto_estimado": bruto_estimado,
            "base_cotizacion": base_cotizacion,
            "salario_bruto": salario_bruto,
            "coste_empresa": coste_empresa,
            "coste_seguridad_social": coste_seguridad_social,
            "base_irpf": base_irpf,
            "coste_irpf": coste_irpf,
            "neto": neto,
            "porcentaje_honorarios_aplicado": porcentaje_honorarios_aplicado,
            "base_despues_honorarios": presupuesto_nomina,
            "base_calculo": base_cotizacion,
        }


class CostPercentageSettings(models.Model):
    contingencias_comunes_empresa = models.DecimalField(max_digits=7, decimal_places=4, default=Decimal("23.6"), verbose_name="Contingencias comunes empresa")
    contingencias_comunes_trabajador = models.DecimalField(max_digits=7, decimal_places=4, default=Decimal("4.7"), verbose_name="Contingencias comunes trabajador")
    mei_empresa = models.DecimalField(max_digits=7, decimal_places=4, default=Decimal("0.75"), verbose_name="MEI empresa")
    mei_trabajador = models.DecimalField(max_digits=7, decimal_places=4, default=Decimal("0.15"), verbose_name="MEI trabajador")
    desempleo_empresa = models.DecimalField(max_digits=7, decimal_places=4, default=Decimal("6"), verbose_name="Desempleo empresa")
    desempleo_trabajador = models.DecimalField(max_digits=7, decimal_places=4, default=Decimal("2"), verbose_name="Desempleo trabajador")
    formacion_empresa = models.DecimalField(max_digits=7, decimal_places=4, default=Decimal("0.6"), verbose_name="Formación empresa")
    formacion_trabajador = models.DecimalField(max_digits=7, decimal_places=4, default=Decimal("0.1"), verbose_name="Formación trabajador")
    at_ep_empresa = models.DecimalField(max_digits=7, decimal_places=4, default=Decimal("1.5"), verbose_name="AT y EP empresa")
    fogasa_empresa = models.DecimalField(max_digits=7, decimal_places=4, default=Decimal("3"), verbose_name="Fondo de garantía salarial empresa")
    porcentaje_honorarios = models.DecimalField(max_digits=7, decimal_places=4, default=Decimal("5"), verbose_name="Honorarios")
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "configuracion_porcentajes"
        verbose_name = "Configuración de porcentajes"
        verbose_name_plural = "Configuración de porcentajes"

    def __str__(self):
        return "Porcentajes globales"

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Artist(models.Model):
    nombre_completo = models.CharField(max_length=255)
    dni_nie = models.CharField(max_length=20, unique=True)
    irpf = models.DecimalField(max_digits=5, decimal_places=2, default=15.00)
    honorario = models.DecimalField(max_digits=7, decimal_places=4, null=True, blank=True, verbose_name="Honorario artista (%)")
    telefono = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    prl = models.BooleanField(default=False, verbose_name="PRL")
    cuenta_bancaria = models.CharField(max_length=34, blank=True)
    numero_seguridad_social = models.CharField(max_length=30)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "artistas"
        verbose_name = "Artista"
        verbose_name_plural = "Artistas"
        ordering = ["nombre_completo"]

    def __str__(self):
        return self.nombre_completo


class ArtistRecord(models.Model):
    class RegistrationType(models.TextChoices):
        SOLO = "SOLO", "Solista"
        BAND = "BAND", "Banda"

    class PaymentStatus(models.TextChoices):
        PAID = "PAID", "Pagado"
        PENDING_INVOICE = "PENDING_INVOICE", "Pendiente pago"
        IN_PROGRESS = "IN_PROGRESS", "En Proceso"
        PARTIAL = "PARTIAL", "Pago a Medias"
        CANCELLED = "CANCELLED", "Anulado"

    artista = models.ForeignKey(Artist, on_delete=models.CASCADE, related_name="registros")
    es_autonomo = models.BooleanField(default=False)
    tipo_irpf = models.DecimalField(max_digits=5, decimal_places=2, default=15.00)
    fecha_alta = models.DateField()
    fecha_baja = models.DateField(null=True, blank=True)
    solicitud_a1 = models.BooleanField(default=False, verbose_name="Solicitud A1")
    proceso_cancelado = models.BooleanField(default=False)
    tipo_registro = models.CharField(max_length=10, choices=RegistrationType.choices, default=RegistrationType.SOLO)
    agrupacion = models.ForeignKey(Grouping, null=True, blank=True, on_delete=models.SET_NULL, related_name="registros_artistas")
    cache_neto = models.DecimalField(max_digits=10, decimal_places=2)
    coste_empresa = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    coste_gestion = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    coste_seguridad_social = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    coste_irpf = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    importe_entregado = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    estado_pago = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.IN_PROGRESS)
    observaciones = models.TextField(blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "registros_artistas"
        verbose_name = "Registro de artista"
        verbose_name_plural = "Registros de artistas"
        ordering = ["-fecha_alta", "-creado_en"]

    def __str__(self):
        return f"{self.artista.nombre_completo} - {self.fecha_alta}"

    def calculate_and_update_costs(self):
        """Calcula y actualiza automáticamente los costos según el tramo y cache_net"""
        porcentajes = CostPercentageSettings.get_solo()
        honorario_artista = None
        if self.artista_id and self.artista and self.artista.honorario is not None:
            honorario_artista = self.artista.honorario

        # Calcular bruto estimado para determinar el tramo correcto (back-calculation)
        porcentaje_honorarios_efectivo = (
            honorario_artista if honorario_artista is not None else porcentajes.porcentaje_honorarios
        )
        porcentaje_empresa_total = (
            porcentajes.contingencias_comunes_empresa
            + porcentajes.mei_empresa
            + porcentajes.desempleo_empresa
            + porcentajes.formacion_empresa
            + porcentajes.at_ep_empresa
            + porcentajes.fogasa_empresa
        )
        factor_empresa = Decimal("1") + porcentaje_empresa_total / Decimal("100")
        comision_previa = self.cache_neto * (porcentaje_honorarios_efectivo / Decimal("100"))
        presupuesto_previo = self.cache_neto - comision_previa
        bruto_estimado = presupuesto_previo / factor_empresa

        bracket = PriceBracket.get_bracket_for_amount(bruto_estimado)
        if bracket:
            costs = bracket.calculate_costs(
                self.cache_neto,
                irpf_percentage=self.tipo_irpf,
                honorarios_percentage=honorario_artista,
            )
            self.coste_empresa = costs["coste_empresa"]
            self.coste_gestion = costs["coste_gestion"]
            self.coste_seguridad_social = costs["coste_seguridad_social"]
            self.coste_irpf = costs["coste_irpf"]

    @property
    def coste_total(self):
        return self.coste_empresa + self.coste_gestion + self.coste_seguridad_social + self.coste_irpf

    @property
    def neto_para_pago(self):
        # Neto = cache_neto - todos los costes (empresa, gestión, SS trabajador, IRPF)
        return self.cache_neto - self.coste_total

    @property
    def importe_pendiente(self):
        pendiente = self.neto_para_pago - self.importe_entregado
        return pendiente if pendiente > 0 else 0
