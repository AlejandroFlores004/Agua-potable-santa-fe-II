from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from . import services


@login_required(login_url='login')
def home_view(request):
    return render(request, 'home.html', services.dashboard_stats())
