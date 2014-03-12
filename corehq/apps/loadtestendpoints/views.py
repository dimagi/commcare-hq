from django.http import HttpResponse
from django_digest.decorators import httpdigest


@httpdigest
def noop(request):
    return HttpResponse('Thanks for submitting', status=201)
