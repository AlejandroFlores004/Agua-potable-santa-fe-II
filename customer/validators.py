import re

from django.core.exceptions import ValidationError

DUI_PATTERN = re.compile(r"^\d{8}-\d$")
PHONE_PATTERN = re.compile(r"^\+?[\d\s-]+$")


def validate_dui(value):
    # Formato 00000000-0; el último dígito es verificador: los 8 primeros se
    # multiplican por 9, 8, ..., 2 y la suma debe cuadrar con él (módulo 10).
    if not DUI_PATTERN.match(value):
        raise ValidationError("El DUI debe tener el formato 00000000-0.")
    digits = [int(digit) for digit in value[:8]]
    total = sum(digit * weight for digit, weight in zip(digits, range(9, 1, -1)))
    if (10 - total % 10) % 10 != int(value[-1]):
        raise ValidationError("El DUI no es válido: revisa los números.")


def validate_phone(value):
    digits = re.sub(r"\D", "", value)
    if not PHONE_PATTERN.match(value) or not 8 <= len(digits) <= 15:
        raise ValidationError("Escribe un teléfono de al menos 8 dígitos, p. ej. 7000-0000.")
