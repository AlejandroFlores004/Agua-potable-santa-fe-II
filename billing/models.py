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

