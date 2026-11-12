from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('asistencia', '0018_reglas_operativas_iniciales')]
    operations = [migrations.AddField(model_name='turnohorario', name='evaluar_tardanzas', field=models.BooleanField(default=False, verbose_name='Evaluar tardanzas', help_text='Actívelo solo si este horario también se usa para controlar puntualidad.'))]
