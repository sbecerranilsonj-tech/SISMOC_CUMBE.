from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('asistencia', '0014_alter_incidenciaasistencia_tipo_and_more')]
    operations = [migrations.AddField(model_name='resumenasistenciadiaria', name='conceptos_editados', field=models.JSONField(default=dict, blank=True))]
