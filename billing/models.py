from django.db import models
from django.contrib.auth.models import User
from connection.models import Line
from datetime import datetime

# Create your models here.
class Fee(models.Model):
    name = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.name} - {self.amount}"
    
    class Meta:
        verbose_name = "Cuota"
        verbose_name_plural = "Cuotas"

class Invoice(models.Model):
    fee = models.ForeignKey(Fee, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    due_date = models.DateField()

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return f"Factura: {self.fee.name} - {self.start_date} al {self.end_date} - Vencimiento: {self.due_date}"
    
    class Meta:
        verbose_name = "Factura"
        verbose_name_plural = "Facturas"

class InvoiceLine(models.Model):
    code = models.CharField(max_length=10, unique=True, blank=True, null=True)
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE)
    line = models.ForeignKey(Line, on_delete=models.CASCADE)
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
    
    def save(self, *args, **kwargs):
        if not self.code:
            super().save(*args, **kwargs)  # Save the instance to get an ID
            self.code = self.code_generator()
        super().save(*args, **kwargs)  # Save again to update the code