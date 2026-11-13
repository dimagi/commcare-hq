from django.http import HttpResponsePermanentRedirect
from django.shortcuts import get_object_or_404

from corehq.apps.short_links.models import ShortLink


def follow_short_link(request, code):
    link = get_object_or_404(ShortLink, code=code)
    return HttpResponsePermanentRedirect(link.target_url)
