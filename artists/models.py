from django.db import models


class Grouping(models.Model):
    nombre = models.CharField(max_length=200, unique=True)
    descripcion = models.TextField(blank=True)
    activo = models.BooleanField(default=True)
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
    porcentaje_empresa = models.DecimalField(max_digits=5, decimal_places=2, help_text="% Costo empresa")
    porcentaje_gestion = models.DecimalField(max_digits=5, decimal_places=2, help_text="% Costo gestión")
    porcentaje_seguridad_social = models.DecimalField(max_digits=5, decimal_places=2, help_text="% Seguridad Social")
    porcentaje_irpf = models.DecimalField(max_digits=5, decimal_places=2, help_text="% IRPF")
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

    def calculate_costs(self, cache_net):
        """Calcula los costos según el tramo"""
        # Para el tramo 1, la base es el cache_net
        # Para otros tramos, se usa la base definida
        base = cache_net if self.numero_tramo == 1 else (self.importe_base or cache_net)

        return {
            "coste_empresa": base * (self.porcentaje_empresa / 100),
            "coste_gestion": base * (self.porcentaje_gestion / 100),
            "coste_seguridad_social": base * (self.porcentaje_seguridad_social / 100),
            "coste_irpf": base * (self.porcentaje_irpf / 100),
        }


class Artist(models.Model):
    nombre_completo = models.CharField(max_length=255)
    dni_nie = models.CharField(max_length=20, unique=True)
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
    solicitud_a1 = models.BooleanField(default=False)
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
        bracket = PriceBracket.get_bracket_for_amount(self.cache_neto)
        if bracket:
            costs = bracket.calculate_costs(self.cache_neto)
            self.coste_empresa = costs["coste_empresa"]
            self.coste_gestion = costs["coste_gestion"]
            self.coste_seguridad_social = costs["coste_seguridad_social"]
            self.coste_irpf = costs["coste_irpf"]

    @property
    def coste_total(self):
        return self.coste_empresa + self.coste_gestion + self.coste_seguridad_social + self.coste_irpf

    @property
    def neto_para_pago(self):
        return self.cache_neto - self.coste_total

    @property
    def importe_pendiente(self):
        pendiente = self.neto_para_pago - self.importe_entregado
        return pendiente if pendiente > 0 else 0
