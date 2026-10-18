from django.shortcuts import render


def messages_response(request, trigger=None):
    """Respuesta estándar de una acción HTMX que terminó (guardar, eliminar, activar...).

    Reemplaza #messages-container por fuera de banda con los mensajes pendientes y,
    si se indica, dispara `trigger` (p. ej. "customerSaved") para que la tabla se recargue.
    Como no trae un modal, el #modal-container que la pidió queda vacío.
    """
    response = render(request, "partials/base/_messages_oob.html")
    if trigger:
        response["HX-Trigger"] = trigger
    return response
