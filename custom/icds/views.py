from django.shortcuts import render
from corehq.apps.hqwebapp.views import render_static


def tableau(request):
    return render(request, 'tableau.html')
