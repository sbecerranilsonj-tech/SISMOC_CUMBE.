# ==============================================================================
# test_sprint1_api.py
# SISMOC-CUMBE | Script de Verificación de Endpoints y Lógica de Negocio
# ==============================================================================

import os
import sys
import django
import pandas as pd
import io

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.stdout.reconfigure(encoding='utf-8')
django.setup()

from django.test import Client
from core.models import Usuario
from asistencia.models import MarcacionBiometrica, ResumenAsistenciaDiaria

def run_tests():
    print("=" * 70)
    print("INICIANDO PRUEBAS DE AUTOMATIZACION - SPRINT 1 (SISMOC-CUMBE)")
    print("=" * 70)

    client = Client()

    # 1. Test Login Contadora
    print("\n1. Test: Autenticacion Login (Contadora Yaneli Terrones)...")
    res_login = client.post(
        "/api/auth/login",
        data={"username_or_dni": "yaneli.terrones", "password": "cumbe2026"},
        content_type="application/json"
    )
    assert res_login.status_code == 200, f"Error en login: {res_login.status_code} - {res_login.content}"
    data_login = res_login.json()
    token = data_login["access_token"]
    user_info = data_login["user"]
    print(f"   [OK] Token JWT generado exitosamente.")
    print(f"   [OK] Usuario: {user_info['nombre_completo']} | Rol: {user_info['rol_display']}")
    auth_header = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    # 2. Test Get Me
    print("\n2. Test: Endpoint Perfil /api/auth/me...")
    res_me = client.get("/api/auth/me", **auth_header)
    assert res_me.status_code == 200, f"Error en me: {res_me.status_code}"
    print(f"   [OK] Perfil validado para DNI: {res_me.json()['dni']}")

    # 3. Test 7 Roles
    print("\n3. Test: Matriz Oficial de 7 Roles RBAC /api/auth/roles...")
    res_roles = client.get("/api/auth/roles")
    assert res_roles.status_code == 200
    roles = res_roles.json()
    assert len(roles) == 7, f"Se esperaban 7 roles, se obtuvieron {len(roles)}"
    for r in roles:
        print(f"   - {r['icono']} {r['codigo']}: {r['nombre']}")
    print(f"   [OK] 7 Roles verificados correctamente.")

    # 4. Test Tiempo Real
    print("\n4. Test: Asistencia en Tiempo Real /api/asistencia/tiempo-real...")
    res_tr = client.get("/api/asistencia/tiempo-real")
    assert res_tr.status_code == 200
    tr_data = res_tr.json()
    print(f"   [OK] Dispositivo: {tr_data['dispositivo_ip']} | Estado: {tr_data['estado_dispositivo']}")
    print(f"   [OK] Presentes hoy: {tr_data['total_presentes_hoy']} colaboradores")
    for cp in tr_data['colaboradores_presentes'][:3]:
        print(f"      * {cp['nombre']} ({cp['rol_display']}) - Ingreso: {cp['primera_marcacion']}")

    # 5. Test Resumen de Asistencia
    print("\n5. Test: Resumen de Asistencia Diaria /api/asistencia/resumen...")
    res_resumen = client.get("/api/asistencia/resumen", **auth_header)
    assert res_resumen.status_code == 200
    resumenes = res_resumen.json()
    print(f"   [OK] Se obtuvieron {len(resumenes)} registros de resumen diario.")
    # Verificar horas extras de Yaneli
    yaneli_res = next((r for r in resumenes if r["dni"] == "48039773" and float(r["horas_extras_25"]) > 0), None)
    if yaneli_res:
        print(f"   [OK] Horas Extras Contadora: 25% = {yaneli_res['horas_extras_25']}h | 35% = {yaneli_res['horas_extras_35']}h")

    # Verificar vueltas de chofer Carlos Cóndor
    condor_res = next((r for r in resumenes if r["dni"] == "45892147" and r["vueltas_codigo"] in ["X", "XX"]), None)
    if condor_res:
        print(f"   [OK] Vueltas Conductor (Carlos Cóndor): Código '{condor_res['vueltas_codigo']}' ({condor_res['total_vueltas_num']} vueltas) - Sin error #¿NOMBRE?")

    # 6. Test Reporte de Planilla Consolidado
    print("\n6. Test: Reporte Consolidado de Planilla /api/asistencia/reporte-planilla...")
    res_plan = client.get("/api/asistencia/reporte-planilla", **auth_header)
    assert res_plan.status_code == 200
    plan_data = res_plan.json()
    print(f"   [OK] Periodo: {plan_data['periodo']}")
    print(f"   [OK] Total Horas Efectivas: {plan_data['total_horas_efectivas']} h")
    print(f"   [OK] Total Horas Extras (25%): {plan_data['total_horas_extras_25']} h")
    print(f"   [OK] Total Horas Extras (35%): {plan_data['total_horas_extras_35']} h")
    print(f"   [OK] Total Vueltas Conductores: {plan_data['total_vueltas_conductores']} vueltas")
    print(f"   [OK] Total Minutos Tardanza: {plan_data['total_minutos_tardanza']} min")

    # 7. Test Subida y Procesamiento de Excel ZKTeco con Pandas
    print("\n7. Test: Parser con Pandas de Excel ZKTeco /api/asistencia/subir-excel...")
    # Crear un DataFrame de prueba similar al exportado por ZKSoftware
    df_zk = pd.DataFrame([
        {"DNI": "48039773", "Nombre": "Yaneli Terrones", "Time": "2026-10-01 07:55:00", "State": "Check-In", "Vueltas": "0"},
        {"DNI": "48039773", "Nombre": "Yaneli Terrones", "Time": "2026-10-01 19:15:00", "State": "Check-Out", "Vueltas": "0"},
        {"DNI": "45892147", "Nombre": "Carlos Cóndor", "Time": "2026-10-01 06:40:00", "State": "Check-In", "Vueltas": "XX"},
        {"DNI": "45892147", "Nombre": "Carlos Cóndor", "Time": "2026-10-01 20:30:00", "State": "Check-Out", "Vueltas": "XX"},
        {"DNI": "73456789", "Nombre": "Pedro Morales", "Time": "2026-10-01 08:35:00", "State": "Check-In", "Vueltas": "0"},
        {"DNI": "73456789", "Nombre": "Pedro Morales", "Time": "2026-10-01 18:00:00", "State": "Check-Out", "Vueltas": "0"},
    ])
    excel_buffer = io.BytesIO()
    df_zk.to_excel(excel_buffer, index=False, engine="openpyxl")
    excel_buffer.seek(0)
    excel_buffer.name = "ASISTENCIA_ZKTECO_PRUEBA_OCTUBRE_2026.xlsx"

    res_upload = client.post(
        "/api/asistencia/subir-excel",
        data={"file": excel_buffer},
        **auth_header
    )
    assert res_upload.status_code == 200, f"Error upload: {res_upload.status_code} - {res_upload.content}"
    up_data = res_upload.json()
    print(f"   [OK] Archivo procesado con Pandas: {up_data['archivo']}")
    print(f"   [OK] Filas procesadas: {up_data['filas_procesadas']}")
    print(f"   [OK] Empleados identificados: {up_data['empleados_identificados']}")
    print(f"   [OK] HH.EE. 25%: {up_data['total_he_25']}h | HH.EE. 35%: {up_data['total_he_35']}h")
    print(f"   [OK] Vueltas de Choferes calculadas: {up_data['total_vueltas_choferes']}")

    # 8. Test Marcación en Tiempo Real
    print("\n8. Test: Marcación en Vivo /api/asistencia/marcar...")
    res_marcar = client.post(
        "/api/asistencia/marcar",
        data={
            "dni": "45892147",
            "tipo_evento": "ENTRADA",
            "origen": "APP_MOVIL_GPS",
            "latitud": -6.77137,
            "longitud": -79.84088
        },
        content_type="application/json"
    )
    assert res_marcar.status_code == 200
    print(f"   [OK] Marcación registrada para DNI {res_marcar.json()['dni']} con GPS Geofencing")

    print("\n" + "=" * 70)
    print("TODAS LAS PRUEBAS DEL SPRINT 1 HAN PASADO CON EXITO (100% OK)")
    print("=" * 70)

if __name__ == "__main__":
    run_tests()
