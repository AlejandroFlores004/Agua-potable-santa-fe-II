from django import forms
from django.contrib.auth.forms import PasswordChangeForm, SetPasswordForm
from django.contrib.auth.models import Group, User
from django.contrib.auth.password_validation import validate_password

from .permissions import MODULES, Level, level_for, set_group_level

INPUT_CLASSES = "input input-bordered w-full"
SELECT_CLASSES = "select select-bordered w-full"
CHECKBOX_CLASSES = "checkbox checkbox-primary checkbox-sm"


def _style_fields(form):
    for field in form.fields.values():
        widget = field.widget
        if isinstance(widget, forms.CheckboxSelectMultiple):
            widget.attrs.setdefault("class", CHECKBOX_CLASSES)
        elif isinstance(widget, forms.CheckboxInput):
            widget.attrs.setdefault("class", "toggle toggle-primary")
        elif isinstance(widget, forms.Select):
            widget.attrs.setdefault("class", SELECT_CLASSES)
        else:
            widget.attrs.setdefault("class", INPUT_CLASSES)


class UserForm(forms.ModelForm):
    groups = forms.ModelMultipleChoiceField(
        label="Grupos",
        queryset=Group.objects.order_by("name"),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    password1 = forms.CharField(label="Contraseña", strip=False, widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    password2 = forms.CharField(label="Confirmar contraseña", strip=False, widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "groups", "is_active", "is_superuser"]
        labels = {
            "username": "Usuario",
            "first_name": "Nombre",
            "last_name": "Apellidos",
            "email": "Correo electrónico",
            "is_active": "Activo",
            "is_superuser": "Administrador total",
        }
        help_texts = {
            "username": "Con este nombre se inicia sesión. Letras, números y @/./+/-/_.",
            "is_active": "Si está desactivado no puede iniciar sesión.",
            "is_superuser": "Tiene todos los permisos sin importar sus grupos.",
        }

    def __init__(self, *args, editor, **kwargs):
        super().__init__(*args, **kwargs)
        self.editor = editor
        is_new = self.instance.pk is None

        # La contraseña solo se pide al crear; después se cambia desde su propio formulario.
        if not is_new:
            del self.fields["password1"]
            del self.fields["password2"]
        # Solo un administrador total puede dar o quitar ese nivel.
        if not editor.is_superuser:
            del self.fields["is_superuser"]
        # Nadie puede desactivarse ni quitarse el nivel de administrador a sí mismo.
        if self.instance.pk == editor.pk:
            for name in ("is_active", "is_superuser"):
                if name in self.fields:
                    self.fields[name].disabled = True
                    self.fields[name].help_text = "No puedes cambiar esto en tu propia cuenta."
        _style_fields(self)

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Las contraseñas no coinciden.")
        return password2

    def _post_clean(self):
        super()._post_clean()
        password = self.cleaned_data.get("password2")
        if password:
            try:
                validate_password(password, self.instance)
            except forms.ValidationError as error:
                self.add_error("password2", error)

    def save(self, commit=True):
        user = super().save(commit=False)
        if "password1" in self.fields:
            user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
            self.save_m2m()
        return user


class AdminSetPasswordForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style_fields(self)


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]
        labels = {"first_name": "Nombre", "last_name": "Apellidos", "email": "Correo electrónico"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style_fields(self)


class ProfilePasswordForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style_fields(self)


class GroupForm(forms.ModelForm):
    """Nombre del grupo y nivel de acceso por módulo (un campo `level_<app>` por cada uno)."""

    class Meta:
        model = Group
        fields = ["name"]
        labels = {"name": "Nombre del grupo"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].widget.attrs["placeholder"] = "Ej. Cobranza"
        permission_ids = set(self.instance.permissions.values_list("pk", flat=True)) if self.instance.pk else set()
        for app_label, label in MODULES:
            current = level_for(permission_ids, app_label)
            choices = [(value, text) for value, text in Level.choices if value != Level.CUSTOM]
            if current == Level.CUSTOM:
                choices.append((Level.CUSTOM, "Personalizado (sin cambios)"))
            self.fields[f"level_{app_label}"] = forms.ChoiceField(label=label, choices=choices, initial=current)
        _style_fields(self)

    @property
    def level_fields(self):
        return [self[f"level_{app_label}"] for app_label, _ in MODULES]

    def save(self, commit=True):
        group = super().save(commit=commit)
        if commit:
            self.save_levels(group)
        return group

    def save_levels(self, group):
        for app_label, _ in MODULES:
            set_group_level(group, app_label, self.cleaned_data[f"level_{app_label}"])
