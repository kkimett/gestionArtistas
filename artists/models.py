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

    @classmethod
    def get_bracket_for_calculator(cls, base_imponible, num_days=1, n_artistas=1, porcentaje_empresa_total=Decimal("0")):
        """Replica la lógica PHP para determinar el tramo a partir de la base diaria estimada."""
        ordered_brackets = list(cls.objects.filter(activo=True).order_by("numero_tramo"))
        if not ordered_brackets:
            return None

        divisor = Decimal(str(num_days)) * Decimal(str(n_artistas))
        if divisor <= 0:
            divisor = Decimal("1")

        base_diaria = (Decimal(str(base_imponible)) * Decimal("0.95")) / divisor

        for tramo in ordered_brackets:
            if tramo.rango_minimo <= base_diaria <= tramo.rango_maximo:
                return tramo

        # Si base_diaria supera el último tramo, devolver el último
        return ordered_brackets[-1]

    def calculate_costs(self, cache_net, irpf_percentage=None, honorarios_percentage=None, num_days=1, n_artistas=1):
        """
        Replica la lógica de la calculadora PHP usando la base imponible introducida.
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
        

        porcentaje_ss_total = porcentaje_empresa_total + porcentaje_trabajador_total

        porcentaje_irpf_aplicado = irpf_percentage if irpf_percentage is not None else Decimal("0")
        base_imponible = Decimal(str(cache_net))


        dias = Decimal(str(num_days))
        artistas = Decimal(str(n_artistas))
        if dias <= 0:
            dias = Decimal("1")
        if artistas <= 0:
            artistas = Decimal("1")

        iva_porcentaje = Decimal("21")
        iva_importe = base_imponible * (iva_porcentaje / Decimal("100"))
        total_con_iva = base_imponible + iva_importe

        factor_reduccion = Decimal("0.95")
        base_diaria_estimada = (base_imponible * factor_reduccion) / (dias * artistas)

        #print(f"base * factor reduccion: {base_imponible} * {factor_reduccion} = {base_imponible * factor_reduccion}")

        if self.numero_tramo == 1:
            base_cotizacion_diaria = base_diaria_estimada / (Decimal("1") + (porcentaje_empresa_total / Decimal("100")))
        else:
            base_cotizacion_diaria = self.importe_base or base_diaria_estimada

        base_cotizacion = base_cotizacion_diaria * dias
        
        #print(f"base_cotizacion: {base_cotizacion}")
        coste_empresa = base_cotizacion * (porcentaje_empresa_total / Decimal("100"))
        coste_seguridad_social = base_cotizacion * (porcentaje_trabajador_total / Decimal("100"))
        coste_ss_total = coste_empresa + coste_seguridad_social

        coste_gestion = base_imponible * (porcentaje_honorarios_aplicado / Decimal("100"))
        salario_bruto = (base_imponible * factor_reduccion) / artistas

        base_irpf = salario_bruto - coste_empresa
        if base_irpf < 0:
            base_irpf = Decimal("0")

        coste_irpf = base_irpf * (porcentaje_irpf_aplicado / Decimal("100"))
        neto = (base_imponible / artistas) - coste_ss_total - (coste_gestion / artistas) - coste_irpf
        if neto < 0:
            neto = Decimal("0")

        neto_total = neto * artistas

        

        return {
            "coste_gestion": coste_gestion,
            "presupuesto_nomina": salario_bruto,
            "base_cotizacion": base_cotizacion,
            "base_cotizacion_diaria": base_cotizacion_diaria,
            "base_diaria_estimada": base_diaria_estimada,
            "salario_bruto": salario_bruto,
            "coste_empresa": coste_empresa,
            "coste_seguridad_social": coste_seguridad_social,
            "coste_ss_total": coste_ss_total,
            "base_irpf": base_irpf,
            "coste_irpf": coste_irpf,
            "neto": neto,
            "neto_total": neto_total,
            "importe_bruto": salario_bruto,
            "base_imponible": base_imponible,
            "iva_porcentaje": iva_porcentaje,
            "iva_importe": iva_importe,
            "total_con_iva": total_con_iva,
            "porcentaje_empresa_total": porcentaje_empresa_total,
            "porcentaje_trabajador_total": porcentaje_trabajador_total,
            "porcentaje_ss_total": porcentaje_ss_total,
            "porcentaje_honorarios_aplicado": porcentaje_honorarios_aplicado,
            "base_despues_honorarios": salario_bruto,
            "base_calculo": base_cotizacion,
        }

    def calculate_costs_from_net(self, neto_liquido, irpf_percentage=None, honorarios_percentage=None):
        """
        Cálculo inverso: dado el neto líquido (lo que recibe el trabajador),
        calcula el salario bruto y todos los costes asociados.
        Usa iteración para resolver el sistema de ecuaciones.
        """
        porcentajes = CostPercentageSettings.get_solo()

        porcentaje_honorarios_aplicado = (
            honorarios_percentage if honorarios_percentage is not None
            else porcentajes.porcentaje_honorarios
        )

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

        porcentaje_irpf_aplicado = irpf_percentage if irpf_percentage is not None else Decimal("0")

        # Iteración para encontrar salario_bruto que, después de descontar SS e IRPF, da el neto
        salario_bruto = neto_liquido  # Aproximación inicial
        for _ in range(100):  # Máximo 100 iteraciones
            coste_seguridad_social = salario_bruto * (porcentaje_trabajador_total / Decimal("100"))
            base_irpf = max(Decimal("0"), salario_bruto - coste_seguridad_social)
            coste_irpf = base_irpf * (porcentaje_irpf_aplicado / Decimal("100"))
            neto_calculado = salario_bruto - coste_seguridad_social - coste_irpf

            # Si converge, salir
            if abs(neto_calculado - neto_liquido) < Decimal("0.01"):
                break

            # Ajustar para la próxima iteración
            if neto_calculado < neto_liquido:
                salario_bruto += (neto_liquido - neto_calculado) * Decimal("1.01")
            else:
                salario_bruto -= (neto_calculado - neto_liquido) * Decimal("1.01")

        # Una vez encontrado salario_bruto, calcular presupuesto_nomina y cache_net
        presupuesto_nomina = salario_bruto + (salario_bruto * (porcentaje_empresa_total / Decimal("100")))
        
        # Calcular base_cotizacion según tramo
        if self.numero_tramo == 1:
            base_cotizacion = presupuesto_nomina
        else:
            base_cotizacion = self.importe_base or presupuesto_nomina

        # Ajustar coste_empresa con la base de cotización correcta
        coste_empresa = base_cotizacion * (porcentaje_empresa_total / Decimal("100"))
        
        # Recalcular presupuesto_nomina con base correcta
        presupuesto_nomina = salario_bruto + coste_empresa
        
        # Cache neto es presupuesto + honorarios
        coste_gestion = presupuesto_nomina * (porcentaje_honorarios_aplicado / Decimal("100"))
        cache_net = presupuesto_nomina + coste_gestion

        # Recalcular valores finales con las bases correctas
        coste_seguridad_social = base_cotizacion * (porcentaje_trabajador_total / Decimal("100"))
        base_irpf = max(Decimal("0"), salario_bruto - coste_seguridad_social)
        coste_irpf = base_irpf * (porcentaje_irpf_aplicado / Decimal("100"))
        neto = salario_bruto - coste_seguridad_social - coste_irpf

        return {
            "coste_gestion": coste_gestion,
            "presupuesto_nomina": presupuesto_nomina,
            "base_cotizacion": base_cotizacion,
            "salario_bruto": salario_bruto,
            "coste_empresa": coste_empresa,
            "coste_seguridad_social": coste_seguridad_social,
            "base_irpf": base_irpf,
            "coste_irpf": coste_irpf,
            "neto": neto,
            "cache_net": cache_net,
            "porcentaje_honorarios_aplicado": porcentaje_honorarios_aplicado,
            "importe_bruto": salario_bruto,  # El importe bruto es el salario_bruto
            "importe_total_empresa": salario_bruto + coste_empresa,  # Total que factura la empresa
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
    destino_a1 = models.CharField(max_length=255, blank=True, verbose_name="Destino A1")
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
        honorario_artista = None
        if self.artista_id and self.artista and self.artista.honorario is not None:
            honorario_artista = self.artista.honorario

        bracket = PriceBracket.get_bracket_for_amount(self.cache_neto)
        if bracket:
            costs = bracket.calculate_costs(
                self.cache_neto,
                irpf_percentage=self.tipo_irpf,
                honorarios_percentage=honorario_artista,
            )
            self.coste_empresa = costs["coste_ss_total"]
            self.coste_gestion = costs["coste_gestion"]
            self.coste_seguridad_social = costs["coste_seguridad_social"]
            self.coste_irpf = costs["coste_irpf"]

    @property
    def coste_total(self):
        return self.coste_empresa + self.coste_gestion + self.coste_irpf

    @property
    def neto_para_pago(self):
        # coste_empresa ya incluye SS empresa + trabajador
        return self.cache_neto - self.coste_total

    @property
    def importe_pendiente(self):
        pendiente = self.neto_para_pago - self.importe_entregado
        return pendiente if pendiente > 0 else 0
