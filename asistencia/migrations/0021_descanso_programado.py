from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('asistencia', '0020_trabajador_nocturnas'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [migrations.CreateModel(
        name='DescansoProgramado',
        fields=[('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('desde', models.DateField()), ('hasta', models.DateField()), ('dias', models.JSONField(default=list)),
                ('creado_el', models.DateTimeField(auto_now_add=True)),
                ('trabajador', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='descansos_programados', to='asistencia.trabajador')),
                ('responsable', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL))],
        options={'ordering': ['-creado_el', '-pk'], 'constraints': [models.CheckConstraint(condition=models.Q(hasta__gte=models.F('desde')), name='descanso_vigencia_valida')]},
    )]
