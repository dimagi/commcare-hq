from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404

from corehq.apps.short_links.models import ShortLink


def follow_short_link(request, code):
    link = get_object_or_404(ShortLink.objects.active(), code=code)
    return HttpResponseRedirect(link.target_url)
