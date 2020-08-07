from django.urls import reverse
from django.utils.translation import ugettext_noop, ugettext as _

from corehq.tabs.uitab import UITab
from custom.icds_core.const import ManageHostedCCZLink_urlname, ManageHostedCCZ_urlname


class HostedCCZTab(UITab):
    title = ugettext_noop('CCZ Hostings')
    url_prefix_formats = (
        '/a/{domain}/ccz/hostings/',
    )
    _is_viewable = False

    @property
    def sidebar_items(self):
        items = super(HostedCCZTab, self).sidebar_items
        items.append((_('Manage CCZ Hostings'), [
            {'url': reverse(ManageHostedCCZLink_urlname, args=[self.domain]),
             'title': _("Manage CCZ Hosting Links")
             },
            {'url': reverse(ManageHostedCCZ_urlname, args=[self.domain]),
             'title': _("Manage CCZ Hosting")
             },
        ]))
        return items
