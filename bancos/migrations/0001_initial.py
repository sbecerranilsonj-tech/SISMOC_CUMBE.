from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import bancos.storage


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name='EstadoCuenta', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('cuenta', models.CharField(max_length=40)),
            ('moneda', models.CharField(default='SOLES', max_length=12)),
            ('inicio', models.DateField()), ('fin', models.DateField()),
            ('saldo_inicial', models.DecimalField(max_digits=16, decimal_places=2)),
            ('saldo_final', models.DecimalField(max_digits=16, decimal_places=2)),
            ('huella', models.CharField(max_length=64, unique=True)),
            ('pdf', models.FileField(storage=bancos.storage.almacen_privado, upload_to='estados/%Y/%m/')),
            ('incidencias', models.JSONField(default=list)),
            ('estado', models.CharField(choices=[('PENDIENTE', 'Pendiente'), ('VALIDADO', 'Validado')], default='PENDIENTE', max_length=12)),
            ('creado', models.DateTimeField(auto_now_add=True)),
            ('validado', models.DateTimeField(blank=True, null=True)),
            ('creado_por', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='estados_importados', to=settings.AUTH_USER_MODEL)),
            ('validado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='estados_validados', to=settings.AUTH_USER_MODEL)),
        ], options={'ordering': ['-inicio', '-pk']}),
        migrations.CreateModel(name='Movimiento', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('orden', models.PositiveIntegerField()), ('pagina', models.PositiveIntegerField()),
            ('fecha', models.DateField()), ('fecha_valor', models.DateField()),
            ('descripcion', models.CharField(max_length=500)),
            ('cargo', models.DecimalField(max_digits=16, decimal_places=2, default=0)),
            ('abono', models.DecimalField(max_digits=16, decimal_places=2, default=0)),
            ('original', models.JSONField(default=dict)),
            ('observacion', models.CharField(blank=True, max_length=500)),
            ('estado_cuenta', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='movimientos', to='bancos.estadocuenta')),
        ], options={'ordering': ['fecha', 'orden'], 'constraints': [models.UniqueConstraint(fields=('estado_cuenta', 'orden'), name='bancos_orden_unico')]}),
        migrations.CreateModel(name='Revision', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('fecha', models.DateTimeField(auto_now_add=True)), ('detalle', models.JSONField(default=dict)),
            ('estado_cuenta', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='revisiones', to='bancos.estadocuenta')),
            ('movimiento', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to='bancos.movimiento')),
            ('responsable', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
        ]),
    ]
