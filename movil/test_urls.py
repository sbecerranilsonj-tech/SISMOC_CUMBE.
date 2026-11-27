from django.urls import path, include
from django.http import HttpResponse
from pathlib import Path
import ast
urlpatterns = [path('movil/', include('movil.urls'))]

# Nombres usados por el marco web, sin importar la API Ninja en el entorno aislado.
def marco(request, **kwargs):
    return HttpResponse('Marco de pruebas')
tree=ast.parse((Path(__file__).resolve().parent.parent/'config'/'urls.py').read_text(encoding='utf-8'))
for node in ast.walk(tree):
    if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='path' and node.args and isinstance(node.args[0],ast.Constant):
        for key in node.keywords:
            if key.arg=='name' and isinstance(key.value,ast.Constant):
                urlpatterns.append(path(node.args[0].value,marco,name=key.value.value))
