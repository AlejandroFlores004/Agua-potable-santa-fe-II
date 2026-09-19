from django.db import migrations

LOCATIONS = ["CASERIO LOS CASTILLOS", "CASERIO LOS LOBOS", "CASERIO EL CABALLITO"]


def match_location(raw):
    normalized = raw.upper()
    if "CASTILL" in normalized:
        return "CASERIO LOS CASTILLOS"
    if "CABALLITO" in normalized:
        return "CASERIO EL CABALLITO"
    if "LOBOS" in normalized or "LOVOS" in normalized:
        return "CASERIO LOS LOBOS"
    return None


def populate_location(apps, schema_editor):
    Location = apps.get_model('connection', 'Location')
    Line = apps.get_model('connection', 'Line')

    locations = {name: Location.objects.create(name=name) for name in LOCATIONS}

    for line in Line.objects.all():
        description = (line.description or "").strip()
        if not description:
            continue

        if " - " in description:
            location_part, note = description.split(" - ", 1)
            note = note.strip()
        else:
            location_part, note = description, ""

        location_name = match_location(location_part)
        if location_name is None:
            continue

        line.location = locations[location_name]
        line.description = note or None
        line.save(update_fields=['location', 'description'])


def reverse_populate_location(apps, schema_editor):
    Location = apps.get_model('connection', 'Location')
    Line = apps.get_model('connection', 'Line')

    for line in Line.objects.select_related('location').filter(location__isnull=False):
        note = (line.description or "").strip()
        line.description = f"{line.location.name} - {note}" if note else line.location.name
        line.location = None
        line.save(update_fields=['location', 'description'])

    Location.objects.filter(name__in=LOCATIONS).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('connection', '0002_location_line_location'),
    ]

    operations = [
        migrations.RunPython(populate_location, reverse_populate_location),
    ]
