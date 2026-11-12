# ==============================================================================
# config/api.py
# SISMOC-CUMBE | Registro Central de la API con Django Ninja
# Similar a la estructura usada en NutriSync (config/api.py)
# ==============================================================================

from ninja import NinjaAPI
from core.api import router as core_router
from asistencia.api import router as asistencia_router

api = NinjaAPI(
    title="SISMOC-CUMBE API",
    version="1.0.0",
    description=(
        "API del Sistema Integrado de Gestión Operativa, Asistencia y Conciliación "
        "para Empresa de Transportes El Cumbe S.A.C. (RUC: 20480397731). "
        "Prácticas Pre Profesionales — Universidad Señor de Sipán (USS) — Ciclo 2026-II."
    ),
)

# Registrar los routers de cada módulo / app
api.add_router("/auth", core_router, tags=["Autenticación y Roles (RBAC)"])
api.add_router("/asistencia", asistencia_router, tags=["Asistencia (ZKTeco + App Móvil)"])
