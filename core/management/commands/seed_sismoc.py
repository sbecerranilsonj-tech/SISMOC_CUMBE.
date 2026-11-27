# ==============================================================================
# core/management/commands/seed_sismoc.py
# SISMOC-CUMBE | Población de Datos Iniciales para Demostración y Pruebas
# Empresa de Transportes El Cumbe S.A.C. — RUC: 20480397731
# ==============================================================================

from datetime import datetime, date, time, timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import Usuario
from asistencia.models import (
    TurnoHorario,
    MarcacionBiometrica,
    ResumenAsistenciaDiaria,
)


class Command(BaseCommand):
    help = "Puebla la base de datos con los 7 Roles RBAC, turnos y asistencias de El Cumbe S.A.C."

    def add_arguments(self, parser):
        parser.add_argument('--demo', action='store_true', help='Generar asistencias ficticias solo en una base de demostración.')

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.NOTICE("[INFO] Iniciando poblacion de datos para SISMOC-CUMBE..."))

        # 1. Crear Turnos Laborales
        turno_admin, _ = TurnoHorario.objects.get_or_create(
            nombre="Administrativo Chiclayo",
            defaults={
                "hora_entrada": time(8, 0),
                "hora_salida": time(18, 0),
                "tolerancia_minutos": 15,
                "hora_inicio_refrigerio": time(13, 0),
                "hora_fin_refrigerio": time(14, 0),
                "es_para_conductores": False,
                "activo": True,
            },
        )

        turno_boleto_m, _ = TurnoHorario.objects.get_or_create(
            nombre="Boletería Turno Mañana",
            defaults={
                "hora_entrada": time(6, 0),
                "hora_salida": time(14, 30),
                "tolerancia_minutos": 10,
                "es_para_conductores": False,
                "activo": True,
            },
        )

        turno_chofer, _ = TurnoHorario.objects.get_or_create(
            nombre="Ruta Interprovincial (Conductores)",
            defaults={
                "hora_entrada": time(7, 0),
                "hora_salida": time(21, 0),
                "tolerancia_minutos": 30,
                "es_para_conductores": True,
                "activo": True,
            },
        )
        self.stdout.write(self.style.SUCCESS("  [OK] Turnos laborales configurados."))

        # 2. Crear los 7 Usuarios representativos de cada Rol
        usuarios_data = [
            {
                "username": "admin",
                "dni": "00000000",
                "first_name": "Nilson",
                "last_name": "Silupu (Admin TI)",
                "email": "admin@elcumbe.pe",
                "rol": Usuario.Rol.ADMINISTRADOR,
                "agencia_sede": "Chiclayo - Terminal Central",
                "is_staff": True,
                "is_superuser": True,
            },
            {
                "username": "yaneli.terrones",
                "dni": "48039773",
                "first_name": "Yaneli Madeleyne",
                "last_name": "Terrones Vásquez (CPC)",
                "email": "contabilidad@elcumbe.pe",
                "rol": Usuario.Rol.CONTADORA,
                "agencia_sede": "Chiclayo - Oficina Principal",
                "is_staff": True,
                "is_superuser": False,
                "zkteco_user_id": 101,
            },
            {
                "username": "gerente.cumbe",
                "dni": "16548920",
                "first_name": "Segundo",
                "last_name": "Ramos (Gerente General)",
                "email": "gerencia@elcumbe.pe",
                "rol": Usuario.Rol.GERENTE_GENERAL,
                "agencia_sede": "Chiclayo - Gerencia General",
                "is_staff": True,
                "is_superuser": False,
                "zkteco_user_id": 102,
            },
            {
                "username": "carlos.condor",
                "dni": "45892147",
                "first_name": "Carlos Alberto",
                "last_name": "Cóndor Mendoza",
                "email": "carlos.condor@elcumbe.pe",
                "rol": Usuario.Rol.CONDUCTOR,
                "agencia_sede": "Ruta Chiclayo - Cajamarca",
                "licencia_conducir": "Q45892147",
                "categoria_licencia": "A-IIIc",
                "is_staff": False,
                "is_superuser": False,
                "zkteco_user_id": 201,
            },
            {
                "username": "juan.chofer",
                "dni": "43981256",
                "first_name": "Juan Manuel",
                "last_name": "Pérez Huamán",
                "email": "juan.chofer@elcumbe.pe",
                "rol": Usuario.Rol.CONDUCTOR,
                "agencia_sede": "Ruta Trujillo - Jaén",
                "licencia_conducir": "Q43981256",
                "categoria_licencia": "A-IIIc",
                "is_staff": False,
                "is_superuser": False,
                "zkteco_user_id": 202,
            },
            {
                "username": "miguel.embarque",
                "dni": "71234567",
                "first_name": "Miguel Ángel",
                "last_name": "Sánchez Farfán",
                "email": "miguel.sanchez@elcumbe.pe",
                "rol": Usuario.Rol.OPERADOR_EMBARQUE,
                "agencia_sede": "Chiclayo - Embarque Terminal",
                "is_staff": False,
                "is_superuser": False,
                "zkteco_user_id": 301,
            },
            {
                "username": "ana.boleteria",
                "dni": "72345678",
                "first_name": "Ana María",
                "last_name": "Torres Ríos",
                "email": "ana.torres@elcumbe.pe",
                "rol": Usuario.Rol.BOLETERIA,
                "agencia_sede": "Chiclayo - Ventanilla 01",
                "is_staff": False,
                "is_superuser": False,
                "zkteco_user_id": 401,
            },
            {
                "username": "pedro.asistente",
                "dni": "73456789",
                "first_name": "Pedro Luis",
                "last_name": "Morales Cieza",
                "email": "pedro.morales@elcumbe.pe",
                "rol": Usuario.Rol.ADMINISTRATIVO,
                "agencia_sede": "Chiclayo - Administración",
                "is_staff": False,
                "is_superuser": False,
                "zkteco_user_id": 501,
            },
        ]

        usuarios_creados = {}
        for u_info in usuarios_data:
            user_obj = Usuario.objects.filter(username=u_info["username"]).first()
            if not user_obj:
                user_obj = Usuario.objects.create_user(
                    username=u_info["username"],
                    dni=u_info["dni"],
                    first_name=u_info["first_name"],
                    last_name=u_info["last_name"],
                    email=u_info["email"],
                    rol=u_info["rol"],
                    agencia_sede=u_info["agencia_sede"],
                    licencia_conducir=u_info.get("licencia_conducir"),
                    categoria_licencia=u_info.get("categoria_licencia", "A-IIIc"),
                    zkteco_user_id=u_info.get("zkteco_user_id"),
                    is_staff=u_info.get("is_staff", False),
                    is_superuser=u_info.get("is_superuser", False),
                )
                user_obj.set_password("cumbe2026")
                user_obj.save()
            usuarios_creados[u_info["username"]] = user_obj

        self.stdout.write(self.style.SUCCESS(f"  [OK] {len(usuarios_creados)} usuarios creados con los 7 roles y contrasena 'cumbe2026'."))

        if not kwargs.get('demo'):
            self.stdout.write(self.style.SUCCESS('[OK] Configuración inicial preparada. No se generan asistencias de demostración.'))
            return

        # 3. Generar Historial de Asistencia de Muestra (Semana actual)
        hoy = timezone.now().date()
        for dia_idx in range(6, -1, -1):
            fecha_dia = hoy - timedelta(days=dia_idx)
            es_domingo = fecha_dia.weekday() == 6

            # Asistencia para la Contadora (CPC. Yaneli Terrones)
            yaneli = usuarios_creados["yaneli.terrones"]
            if not es_domingo:
                hora_in = time(7, 58)
                hora_out = time(19, 30)  # Hizo horas extras!
                ResumenAsistenciaDiaria.objects.update_or_create(
                    usuario=yaneli,
                    fecha=fecha_dia,
                    defaults={
                        "primera_entrada": hora_in,
                        "ultima_salida": hora_out,
                        "minutos_tardanza": 0,
                        "horas_trabajadas": Decimal("10.50"),
                        "horas_extras_25": Decimal("2.00"),
                        "horas_extras_35": Decimal("0.50"),
                        "horas_nocturnas": Decimal("0.00"),
                        "vueltas_codigo": "0",
                        "total_vueltas_num": 0,
                        "estado": ResumenAsistenciaDiaria.EstadoAsistencia.ASISTIO,
                        "observaciones": "Cierre contable conciliación BCP — Horas Extras aprobadas",
                        "verificado_contabilidad": True,
                    },
                )
                # Crear marcación de entrada
                MarcacionBiometrica.objects.get_or_create(
                    dni=yaneli.dni,
                    fecha_hora=datetime.combine(fecha_dia, hora_in),
                    defaults={
                        "usuario": yaneli,
                        "nombre_empleado": yaneli.nombre_completo,
                        "tipo_evento": MarcacionBiometrica.TipoEvento.ENTRADA,
                        "origen": MarcacionBiometrica.OrigenMarcacion.ZKTECO_EN_LINEA,
                        "dispositivo_ip": "192.168.10.202",
                    },
                )

            # Asistencia para Conductor Principal (Carlos Cóndor)
            carlos = usuarios_creados["carlos.condor"]
            if dia_idx % 2 == 0 and not es_domingo:
                # Vuelta Doble (XX)
                ResumenAsistenciaDiaria.objects.update_or_create(
                    usuario=carlos,
                    fecha=fecha_dia,
                    defaults={
                        "primera_entrada": time(6, 45),
                        "ultima_salida": time(20, 15),
                        "minutos_tardanza": 0,
                        "horas_trabajadas": Decimal("13.50"),
                        "horas_extras_25": Decimal("0.00"),
                        "horas_extras_35": Decimal("0.00"),
                        "horas_nocturnas": Decimal("0.00"),
                        "vueltas_codigo": "XX",
                        "total_vueltas_num": 2,
                        "estado": ResumenAsistenciaDiaria.EstadoAsistencia.ASISTIO,
                        "observaciones": "Ruta Chiclayo - Cajamarca - Chiclayo (Vuelta Doble)",
                        "verificado_contabilidad": True,
                    },
                )
            elif not es_domingo:
                # Vuelta Simple (X)
                ResumenAsistenciaDiaria.objects.update_or_create(
                    usuario=carlos,
                    fecha=fecha_dia,
                    defaults={
                        "primera_entrada": time(7, 30),
                        "ultima_salida": time(14, 0),
                        "minutos_tardanza": 0,
                        "horas_trabajadas": Decimal("6.50"),
                        "horas_extras_25": Decimal("0.00"),
                        "horas_extras_35": Decimal("0.00"),
                        "horas_nocturnas": Decimal("0.00"),
                        "vueltas_codigo": "X",
                        "total_vueltas_num": 1,
                        "estado": ResumenAsistenciaDiaria.EstadoAsistencia.ASISTIO,
                        "observaciones": "Ruta Chiclayo - Cajamarca (Vuelta Simple)",
                        "verificado_contabilidad": True,
                    },
                )
            else:
                # Descanso SUTRAN (8h+)
                ResumenAsistenciaDiaria.objects.update_or_create(
                    usuario=carlos,
                    fecha=fecha_dia,
                    defaults={
                        "primera_entrada": None,
                        "ultima_salida": None,
                        "minutos_tardanza": 0,
                        "horas_trabajadas": Decimal("0.00"),
                        "horas_extras_25": Decimal("0.00"),
                        "horas_extras_35": Decimal("0.00"),
                        "horas_nocturnas": Decimal("0.00"),
                        "vueltas_codigo": "DESCANSO",
                        "total_vueltas_num": 0,
                        "estado": ResumenAsistenciaDiaria.EstadoAsistencia.DESCANSO_SUTRAN,
                        "observaciones": "Cumplimiento reglamentario descanso de 8 horas continuas (SUTRAN)",
                        "verificado_contabilidad": True,
                    },
                )

            # Asistencia para Pedro Morales (Administrativo con una tardanza de muestra)
            pedro = usuarios_creados["pedro.asistente"]
            if not es_domingo:
                es_tardanza = (dia_idx == 1)
                hora_in = time(8, 28) if es_tardanza else time(8, 5)
                min_tard = 28 if es_tardanza else 0
                ResumenAsistenciaDiaria.objects.update_or_create(
                    usuario=pedro,
                    fecha=fecha_dia,
                    defaults={
                        "primera_entrada": hora_in,
                        "ultima_salida": time(18, 0),
                        "minutos_tardanza": min_tard,
                        "horas_trabajadas": Decimal("8.00"),
                        "horas_extras_25": Decimal("0.00"),
                        "horas_extras_35": Decimal("0.00"),
                        "horas_nocturnas": Decimal("0.00"),
                        "vueltas_codigo": "0",
                        "total_vueltas_num": 0,
                        "estado": ResumenAsistenciaDiaria.EstadoAsistencia.TARDANZA if es_tardanza else ResumenAsistenciaDiaria.EstadoAsistencia.ASISTIO,
                        "observaciones": "Tardanza de 28 minutos registrada por biométrico" if es_tardanza else "Jornada ordinaria normal",
                    },
                )

        self.stdout.write(self.style.SUCCESS("  [OK] Historial de marcaciones y resumenes de asistencia poblados."))
        self.stdout.write(self.style.SUCCESS("[SUCCESS] Poblacion de datos de SISMOC-CUMBE finalizada con exito!"))
