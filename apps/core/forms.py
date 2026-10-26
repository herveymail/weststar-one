"""Builds the add/edit form for any registered module straight from its model."""
from django import forms
from django.forms import inlineformset_factory, modelform_factory

from .models import EncryptedField, set_secret
from .permissions import can
from .registry import Module

SYSTEM_FIELDS = {"id", "created_by", "created_at", "updated_at", "archived_at", "legacy_id", "imported_at"}


class StyledMixin:
    def style(self):
        for name, f in self.fields.items():
            w = f.widget
            if isinstance(w, forms.CheckboxInput):
                w.attrs["class"] = "checkbox"
            elif isinstance(w, forms.Select):
                w.attrs["class"] = "select"
            elif isinstance(w, forms.Textarea):
                w.attrs.update({"class": "textarea", "rows": 4})
            else:
                w.attrs["class"] = "input"
            w.attrs.setdefault("id", f"f-{name}")


def encrypted_fields(model) -> list[str]:
    return [f.name for f in model._meta.get_fields() if isinstance(f, EncryptedField)]


def build_form_class(module: Module, user):
    model = module.model
    secrets = encrypted_fields(model)
    exclude = set(SYSTEM_FIELDS) | set(module.form_exclude) | set(secrets)
    if module.owner_scoped:
        exclude.add("user")  # always the person who created it
    # Only managers may change the status of private records (time off, timeclock): no self-approval.
    if module.owner_scoped and not can(user, module.area, "manage") and module.status_field:
        exclude.add(module.status_field)
    fields = [f.name for f in model._meta.get_fields() if getattr(f, "editable", False) and not f.auto_created and f.concrete and f.name not in exclude]
    if "tax_rate" in fields and "client" in fields:  # invoices / quotes: client first, tax rate after the dates
        fields.remove("tax_rate")
        fields.insert(min(len(fields), next((i + 1 for i, x in enumerate(fields) if x in ("due_date", "expires_on")), len(fields))), "tax_rate")
    widgets = {}
    for f in model._meta.get_fields():
        if f.name in fields and f.get_internal_type() == "DateField":
            widgets[f.name] = forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
        if f.name in fields and f.get_internal_type() == "DateTimeField":
            widgets[f.name] = forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M")
    base = modelform_factory(model, fields=fields, widgets=widgets)

    class ModuleForm(StyledMixin, base):
        secret_fields = secrets

        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            for name in secrets:
                label = model._meta.get_field(name).verbose_name
                has = bool(getattr(self.instance, name, ""))
                self.fields[name] = forms.CharField(
                    label=str(label)[:1].upper() + str(label)[1:], required=False, max_length=5000, strip=False,
                    widget=forms.PasswordInput(render_value=False, attrs={"autocomplete": "new-password", "placeholder": "Saved — type to replace" if has else "Not set"}),
                )
                self.fields[name].is_secret = True
                self.fields[name].secret_is_set = has
            # Pickers only offer active (not archived) records.
            for name, f in self.fields.items():
                qs = getattr(f, "queryset", None)
                if qs is not None and hasattr(qs.model, "archived_at"):
                    current = getattr(self.instance, f"{name}_id", None)
                    f.queryset = qs.filter(archived_at__isnull=True) | qs.filter(pk=current) if current else qs.filter(archived_at__isnull=True)
                if qs is not None and qs.model.__name__ == "User":
                    f.queryset = qs.filter(is_active=True)
            self.style()

        def save(self, commit=True):
            obj = super().save(commit=False)
            for name in secrets:
                value = self.cleaned_data.get(name)
                if value:  # blank = keep what's saved
                    set_secret(obj, name, value)
            if commit:
                obj.save()
                self.save_m2m()
            return obj

    return ModuleForm


def build_line_formset(module: Module):
    if not module.lines:
        return None
    line_model, fk = module.lines

    class LineForm(StyledMixin, forms.ModelForm):
        class Meta:
            model = line_model
            fields = ["description", "qty", "rate", "taxable"]

        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            self.style()

    return inlineformset_factory(module.model, line_model, form=LineForm, fk_name=fk, extra=1, can_delete=True, max_num=500, validate_max=True)
