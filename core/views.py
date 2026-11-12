# ==============================================================================
# core/views.py
# SISMOC-CUMBE | Vistas de Autenticacion (Login/Logout) y Dashboard (Sprint 1)
# Empresa de Transportes El Cumbe S.A.C. - RUC: 20480397731
# ==============================================================================

from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from core.models import Usuario
from asistencia.models import MarcacionBiometrica, ResumenAsistenciaDiaria, TurnoHorario
from asistencia.services.zkteco_live import ZKTecoLiveClient
from asistencia.views import contexto_asistencia, datos_registros_huellero
from asistencia.services.revision import puede_gestionar


def login_view(request):
    """
    Vista de Inicio de Sesion institucional para Transportes El Cumbe S.A.C.
    Permite autenticacion tanto por DNI (8 digitos) como por Nombre de Usuario,
    soportando los 7 Roles Oficiales del sistema RBAC.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        identificador = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()

        if not identificador or not password:
            messages.error(request, 'Por favor ingrese su DNI/Usuario y su Contrasena.')
            return render(request, 'login.html')

        # Buscar usuario primero por DNI, luego por Username
        usuario_target = Usuario.objects.filter(dni=identificador).first()
        if not usuario_target:
            usuario_target = Usuario.objects.filter(username=identificador).first()

        username_auth = usuario_target.username if usuario_target else identificador

        user = authenticate(request, username=username_auth, password=password)

        if user is not None:
            if not user.esta_activo or not user.is_active:
                messages.error(
                    request,
                    f'La cuenta de {user.get_full_name() or user.username} se encuentra inactiva. Contacte a Administracion TI.'
                )
                return render(request, 'login.html')

            login(request, user)
            messages.success(
                request,
                f'Bienvenido(a), {user.first_name or user.username}! Ha ingresado con el rol: {user.get_rol_display()}.',
                extra_tags='welcome'
            )
            next_url = request.GET.get('next') or request.POST.get('next') or 'dashboard'
            return redirect(next_url)
        else:
            messages.error(
                request,
                'Credenciales incorrectas. Verifique que su DNI o Usuario y Contrasena sean validos.'
            )

    return render(request, 'login.html')


def logout_view(request):
    """
    Vista de Cierre de Sesion seguro.
    Elimina la sesion activa del usuario y redirige a la pagina de login con mensaje informativo.
    """
    nombre_usuario = request.user.first_name or request.user.username if request.user.is_authenticated else 'Usuario'
    logout(request)
    messages.info(request, f'Sesion finalizada correctamente. Hasta pronto, {nombre_usuario}!')
    return redirect('login')


@login_required(login_url='login')
def dashboard_view(request):
    """Vista web principal para monitoreo en vivo de SISMOC-CUMBE."""
    if getattr(settings,'MOVIL_HABILITADO',True) and request.user.rol == 'BOLETERIA' and request.GET.get('vista','dashboard')=='dashboard':
        return redirect('movil_ventas')
    # Consultar registros guardados; abrir la página no crea ni sincroniza marcas.
    client = ZKTecoLiveClient()
    vista = request.GET.get('vista', 'dashboard')
    info_huellero = client.consultar_registros_locales() if vista in {'dashboard', 'huellero'} else {'colaboradores_presentes': [], 'total_presentes_hoy': 0}
    if not puede_gestionar(request.user):
        info_huellero['colaboradores_presentes'] = [c for c in info_huellero['colaboradores_presentes'] if c['dni'] == request.user.dni]
        info_huellero['total_presentes_hoy'] = len(info_huellero['colaboradores_presentes'])

    # Resumen general para la cabecera
    total_usuarios = Usuario.objects.filter(esta_activo=True).count() if puede_gestionar(request.user) else 1
    conductores = Usuario.objects.filter(rol=Usuario.Rol.CONDUCTOR, esta_activo=True)
    if not puede_gestionar(request.user):
        conductores = conductores.filter(pk=request.user.pk)
    total_conductores = conductores.count()
    resumenes_recientes = ResumenAsistenciaDiaria.objects.select_related('usuario').order_by('-fecha')[:25]
    if not puede_gestionar(request.user):
        resumenes_recientes = ResumenAsistenciaDiaria.objects.filter(usuario=request.user).order_by('-fecha')[:25]
    turnos = TurnoHorario.objects.filter(activo=True)

    context = {
        'empresa_nombre': 'EMPRESA DE TRANSPORTES EL CUMBE S.A.C.',
        'empresa_ruc': '20480397731',
        'info_huellero': info_huellero,
        'total_usuarios': total_usuarios,
        'total_conductores': total_conductores,
        'resumenes_recientes': resumenes_recientes,
        'turnos': turnos,
        'roles': Usuario.Rol.choices,
        'registros_huellero': datos_registros_huellero(request.user) if vista == 'huellero' else [],
    }
    context.update(contexto_asistencia(request))
    if vista == 'personal':
        from asistencia.views_personal import contexto_personal
        context.update(contexto_personal(request))
    return render(request, 'index.html', context)
