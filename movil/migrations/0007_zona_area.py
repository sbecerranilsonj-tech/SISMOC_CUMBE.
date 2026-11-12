from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('movil', '0006_identidad_conductor_opcional')]
    operations = [migrations.AddField(model_name='zona', name='area', field=models.CharField(blank=True, max_length=150))]
