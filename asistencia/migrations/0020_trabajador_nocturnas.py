from django.db import migrations, models
class Migration(migrations.Migration):
    dependencies = [('asistencia', '0019_turno_evaluar_tardanzas')]
    operations = [migrations.AddField(model_name='trabajador', name='calcular_nocturnas', field=models.BooleanField(null=True,blank=True,default=None,verbose_name='Calcular horas nocturnas automáticamente'))]
