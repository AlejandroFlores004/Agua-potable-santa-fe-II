from django.db import models
from django.contrib.auth.models import User

# Create your models here.
class Customer(models.Model):
    dui = models.CharField("DUI", max_length=10, unique=True, blank=True, null=True, default="00000000-0")
    firstName = models.CharField("Nombre", max_length=255)
    lastName = models.CharField("Apellido", max_length=255)
    email = models.EmailField("Correo electrónico", unique=True, blank=True, null=True, default="cliente@example.com")
    number = models.CharField("Número de teléfono", max_length=20, blank=True, null=True, default="0000-0000")
    created_at = models.DateTimeField("Fecha de creación", auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Creado por")
    edited_at = models.DateTimeField("Fecha de edición", auto_now=True)

    def __str__(self):
        return f"{self.firstName} {self.lastName}"

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
