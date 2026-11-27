from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies=[('movil','0007_zona_area')]
    operations=[
        migrations.AddField(model_name='operacion',name='distribucion_asientos',field=models.JSONField(default=dict,blank=True)),
        migrations.AddField(model_name='pasajero',name='punto_desembarque',field=models.CharField(max_length=150,blank=True,default='')),
    ]
