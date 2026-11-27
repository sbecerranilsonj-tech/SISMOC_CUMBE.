"""Bosquejos del IQ2: datos ficticios y simulaciones sin escrituras en el servidor."""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.http import require_GET


@login_required(login_url="login")
@require_GET
def prototipos_iq2(request):
    return render(request, "core/prototipos_iq2.html")
