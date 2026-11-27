from django.urls import path
from core.deployment import health, archivo_media

urlpatterns=[path('health/',health),path('media/<path:path>',archivo_media)]
