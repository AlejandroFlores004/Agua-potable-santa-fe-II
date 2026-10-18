from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.auth.models import User
from connection.models import Line
from datetime import datetime

# Create your models here.
class Account(models.Model):
    name = models.CharField("Nombre de cuenta", max_length=100)
    number = models.CharField("Número de cuenta", max_length=50, unique=True)

    created_at = models.DateTimeField("Fecha de creación", auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Creado por")

    def __str__(self):
        return f"{self.name} - {self.number}"

    class Meta:
        verbose_name = "Cuenta"
        verbose_name_plural = "Cuentas"

class Fee(models.Model):
    name = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    isActive = models.BooleanField("Activa", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.name} - {self.amount}"
    
    class Meta:
        verbose_name = "Cuota"
        verbose_name_plural = "Cuotas"

class LateFee(models.Model):
    name = models.CharField("Nombre", max_length=100)
    amount = models.DecimalField("Monto", max_digits=10, decimal_places=2)
    # Solo una mora puede ser la de por defecto: es la que se aplica a los
    # recibos nuevos que arrastran saldo de un recibo anterior sin pagar.
    isDefault = models.BooleanField("Por defecto", default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.name} - {self.amount}"

    @classmethod
    def get_default(cls):
        return cls.objects.filter(isDefault=True).first()

    def make_default(self):
        LateFee.objects.exclude(pk=self.pk).filter(isDefault=True).update(isDefault=False)
        if not self.isDefault:
            self.isDefault = True
            self.save(update_fields=["isDefault"])

    class Meta:
        verbose_name = "Mora"
        verbose_name_plural = "Moras"

class Invoice(models.Model):
    # Una factura nace en borrador (se asignan líneas e imprimen recibos), se abre
    # cuando se entregan los recibos (desde ahí se cobra y puede vencer) y se cierra
    # al terminar el periodo. Solo puede haber una factura abierta a la vez.
    class Status(models.TextChoices):
        DRAFT = "draft", "Borrador"
        OPEN = "open", "Abierta"
        CLOSED = "closed", "Cerrada"

    account = models.ForeignKey(Account, on_delete=models.CASCADE, verbose_name="Cuenta")
    start_date = models.DateField()
    end_date = models.DateField()
    due_date = models.DateField()
    status = models.CharField("Estado", max_length=10, choices=Status.choices, default=Status.DRAFT)

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.title} - Vencimiento: {self.due_date}"

    @property
    def title(self):
        return f"Factura {self.start_date:%d/%m/%Y} al {self.end_date:%d/%m/%Y}"

    @property
    def is_draft(self):
        return self.status == self.Status.DRAFT

    @property
    def is_open(self):
        return self.status == self.Status.OPEN

    @property
    def is_closed(self):
        return self.status == self.Status.CLOSED

    @classmethod
    def get_open(cls):
        return cls.objects.filter(status=cls.Status.OPEN).first()

    def open(self):
        if not self.is_draft:
            raise ValidationError("Solo se puede abrir una factura en borrador.")
        current = Invoice.get_open()
        if current:
            raise ValidationError(f"Primero cierra la {current.title.lower()}; solo puede haber una factura abierta.")
        self.status = self.Status.OPEN
        self.save(update_fields=["status"])

    def close(self):
        if not self.is_open:
            raise ValidationError("Solo se puede cerrar una factura abierta.")
        self.status = self.Status.CLOSED
        self.save(update_fields=["status"])

    class Meta:
        verbose_name = "Factura"
        verbose_name_plural = "Facturas"
        constraints = [
            models.UniqueConstraint(
                fields=["status"],
                condition=models.Q(status="open"),
                name="billing_single_open_invoice",
            ),
        ]

class InvoiceLine(models.Model):
    code = models.CharField(max_length=10, unique=True, blank=True, null=True)
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE)
    line = models.ForeignKey(Line, on_delete=models.CASCADE)
    fee = models.ForeignKey(Fee, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Cuota")
    # Snapshot of the fee amount at assignment time, so later changes to the
    # line's fee (or the fee itself) don't alter receipts already issued.
    amount = models.DecimalField("Monto", max_digits=10, decimal_places=2, default=0)
    # Total de los recibos anteriores sin pagar de esta línea que se trasladaron a este recibo.
    previous_balance = models.DecimalField("Saldo anterior", max_digits=10, decimal_places=2, default=0)
    late_fee = models.ForeignKey(LateFee, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Mora")
    # Snapshot del monto de la mora, igual que `amount` con la cuota.
    late_fee_amount = models.DecimalField("Monto de mora", max_digits=10, decimal_places=2, default=0)
    # Recibo posterior que absorbió el saldo de este. Si ese recibo se quita, vuelve a quedar pendiente.
    carried_to = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="carried_lines", verbose_name="Trasladado a",
    )
    isPaid = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return f"Factura de linea: {self.code} - Linea: {self.line.code} - cliente: {self.line.customer.firstName} {self.line.customer.lastName} - Pagada: {self.isPaid}"
    
    class Meta:
        verbose_name = "Factura de Linea"
        verbose_name_plural = "Facturas de Lineas"

    
    def code_generator(self):
        return f"{datetime.now().year}-{self.line.code}-{self.id}"
    
    @property
    def total(self):
        return self.amount + self.previous_balance + self.late_fee_amount

    @property
    def is_carried(self):
        return self.carried_to_id is not None

    def set_late_fee(self, late_fee):
        self.late_fee = late_fee
        self.late_fee_amount = late_fee.amount if late_fee else 0

    def _unpaid_previous_lines(self):
        return InvoiceLine.objects.filter(
            line=self.line,
            isPaid=False,
            carried_to__isnull=True,
            invoice__start_date__lt=self.invoice.start_date,
        ).exclude(pk=self.pk)

    def save(self, *args, **kwargs):
        unpaid_previous = None
        if self._state.adding:
            if self.fee_id is None and self.line.fee_id:
                self.fee = self.line.fee
                self.amount = self.line.fee.amount
            unpaid_previous = list(self._unpaid_previous_lines())
            if unpaid_previous:
                self.previous_balance = sum(line.total for line in unpaid_previous)
                if self.late_fee_id is None:
                    self.set_late_fee(LateFee.get_default())
        if not self.code:
            super().save(*args, **kwargs)  # Save the instance to get an ID
            self.code = self.code_generator()
            kwargs.pop("force_insert", None)
        super().save(*args, **kwargs)  # Save again to update the code
        if unpaid_previous:
            InvoiceLine.objects.filter(pk__in=[line.pk for line in unpaid_previous]).update(carried_to=self)

# Create your models here.
