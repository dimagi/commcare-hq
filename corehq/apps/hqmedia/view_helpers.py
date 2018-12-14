from __future__ import absolute_import
from __future__ import unicode_literals

import six

from collections import defaultdict

from django.utils.translation import ugettext as _


def download_multimedia_paths_rows(app):
    paths = defaultdict(list)
    for ref in app.all_media():
        paths[ref.path].append(ref)

    def _readable_ref(ref):
        readable = _("Menu {index}: {name}").format(index=ref.module_id, name=ref.get_module_name())
        if ref.form_id is not None:
            readable += _(" > Form {index}: {name}").format(index=ref.form_order, name=ref.get_form_name())
        return readable

    rows = []
    for path, refs in six.iteritems(paths):
        rows.append((_("Paths"), [path] + [_readable_ref(r) for r in refs]))

    return rows
