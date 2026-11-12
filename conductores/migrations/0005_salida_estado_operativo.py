from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('conductores', '0004_alter_situacionconductor_motivo_and_more')]
    operations = [migrations.AddField(model_name='salida', name='estado_operativo', field=models.CharField(max_length=10, default='AUTO', choices=[('AUTO', 'Según reporte'), ('REALIZADO', 'Salida realizada'), ('CANCELADO', 'Salida cancelada')]))]
