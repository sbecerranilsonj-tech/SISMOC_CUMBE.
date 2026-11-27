from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('asistencia', '0027_dias_sin_trabajo_programado'),
    ]

    operations = [
        migrations.AddField(
            model_name='marcacionbiometrica',
            name='sede',
            field=models.CharField(blank=True, db_index=True, max_length=120,
                                   verbose_name='Sede del equipo que registró la marca'),
        ),
    ]
