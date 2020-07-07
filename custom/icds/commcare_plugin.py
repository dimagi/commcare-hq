from django.urls import reverse

from django.utils.translation import ugettext as _

from corehq import toggles
from custom.icds_core.const import ManageHostedCCZ_urlname


def uitab_dropdown_items(tab, domain, request):
    if tab == 'ApplicationsTab' and toggles.MANAGE_CCZ_HOSTING.enabled_for_request(request):
        return {
            "title": _("Manage CCZ Hosting"),
            "url": reverse(ManageHostedCCZ_urlname, args=[domain]),
        }
