from django.db import models
from customer.models import Customer
from django.contrib.auth.models import User

# Create your models here.
class Line(models.Model):
    code = models.CharField("Código", max_length=100, unique=True, blank=True, null=True)
    description = models.TextField("Descripción", blank=True, null=True)
    created_at = models.DateTimeField("Fecha de creación", auto_now_add=True)
    updated_at = models.DateTimeField("Fecha de edición", auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Creado por")
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='lines')

    def __str__(self):
        return f"{self.code}"

    class Meta:
        verbose_name = "Línea"
        verbose_name_plural = "Líneas"
        ordering = ['-created_at']
    
    def generate_code(self):
        # Generar un código único basado en el ID del objeto
        return f"""{self.customer.firstName[:1].upper()}{self.customer.lastName[:1].upper()}{self.id:04d}"""
    
    def save(self, *args, **kwargs):
        # Si el código no está definido, generarlo automáticamente
        if not self.code:
            super().save(*args, **kwargs)  # Guardar primero para obtener un ID
            self.code = self.generate_code()
            super().save(update_fields=['code'])  # Guardar solo el campo 'code'
        else:
            super().save(*args, **kwargs)
