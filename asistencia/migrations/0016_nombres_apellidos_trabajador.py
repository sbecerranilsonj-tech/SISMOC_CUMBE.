from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("asistencia", "0015_conceptos_editados")]

    operations = [
        migrations.AddField(model_name="trabajador", name="nombres", field=models.CharField(max_length=75, blank=True, default="")),
        migrations.AddField(model_name="trabajador", name="apellido_paterno", field=models.CharField("Primer apellido", max_length=50, blank=True, default="")),
        migrations.AddField(model_name="trabajador", name="apellido_materno", field=models.CharField("Segundo apellido", max_length=50, blank=True, default="")),
    ]
