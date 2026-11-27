"""Rutas aisladas para probar navegación sin cargar extensiones nativas de Ninja."""
import ast
from pathlib import Path
from django.urls import path
from django.http import HttpResponse
from core.views import dashboard_view,login_view,logout_view

def stub(request,**kwargs):return HttpResponse('Ruta de pruebas')
urlpatterns=[path('',dashboard_view,name='dashboard'),path('login/',login_view,name='login'),path('logout/',logout_view,name='logout')]
tree=ast.parse((Path(__file__).resolve().parent.parent/'config/urls.py').read_text(encoding='utf-8'))
for node in ast.walk(tree):
    if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='path' and node.args and isinstance(node.args[0],ast.Constant):
        route=node.args[0].value
        for key in node.keywords:
            if key.arg=='name' and isinstance(key.value,ast.Constant) and key.value.value not in ['dashboard','login','logout'] and not key.value.value.startswith('movil_') and not route.startswith(('movil/','api/')):
                urlpatterns.append(path(route,stub,name=key.value.value))
