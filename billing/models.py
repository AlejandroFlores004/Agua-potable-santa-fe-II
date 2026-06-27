from django.db import models
from django.contrib.auth.models import User

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