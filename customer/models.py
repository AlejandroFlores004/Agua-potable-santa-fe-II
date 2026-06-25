from django.db import models
from django.contrib.auth.models import User

# Create your models here.
class Customer(models.Model):
    dui = models.CharField("DUI", max_length=10, unique=True, blank=True, null=True)
    firstName = models.CharField("Nombre", max_length=255)
    lastName = models.CharField("Apellido", max_length=255)
    email = models.EmailField("Correo electrónico", unique=True, blank=True, null=True)
    number = models.CharField("Número de teléfono", max_length=20, blank=True, null=True)
    created_at = models.DateTimeField("Fecha de creación", auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Creado por")

    def __str__(self):
        return f"{self.firstName} {self.lastName}"

    class Meta:
        name = "Cliente"
        verbose_name_plural = "Clientes"
