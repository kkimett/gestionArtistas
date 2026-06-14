from django.db import models

from artists.models import Artist


class Invoice(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Borrador"
        ISSUED = "ISSUED", "Emitida"
        PAID = "PAID", "Cobrada"
        PARTIAL = "PARTIAL", "Pago a Medias"
        CANCELLED = "CANCELLED", "Anulada"

    artista = models.ForeignKey(Artist, on_delete=models.CASCADE, related_name="facturas")
    referencia = models.CharField(max_length=80, unique=True)
    fecha_factura = models.DateField()
    fecha_vencimiento = models.DateField(null=True, blank=True)
    fecha_cobro = models.DateField(null=True, blank=True)
    importe = models.DecimalField(max_digits=10, decimal_places=2)
    estado = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    notas = models.TextField(blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "facturas"
        verbose_name = "Factura"
        verbose_name_plural = "Facturas"
        ordering = ["-fecha_factura", "referencia"]

    def __str__(self):
        return f"{self.referencia} - {self.artista.nombre_completo}"
