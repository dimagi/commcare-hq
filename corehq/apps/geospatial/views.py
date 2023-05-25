from django.http import HttpResponseRedirect
from django.utils.translation import gettext_lazy as _

from corehq.apps.geospatial.reports import CaseManagementMap


def geospatial_default(request, *args, **kwargs):
    return HttpResponseRedirect(CaseManagementMap.get_url(*args, **kwargs))
