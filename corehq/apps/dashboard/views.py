from django.http import HttpResponse


def dashboard_default(request, domain):
    return HttpResponse("it twerks!")
