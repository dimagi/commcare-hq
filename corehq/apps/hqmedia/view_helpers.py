from __future__ import absolute_import
from __future__ import unicode_literals

import six

from collections import defaultdict

from django.utils.translation import ugettext as _

from corehq.apps.app_manager.views.media_utils import interpolate_media_path


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


def validate_multimedia_paths_rows(app, rows):
    old_paths_last_seen = {i.path: None for i in app.all_media()}
    new_paths_last_seen = defaultdict(lambda: None)

    valid_count = 0
    errors = []
    warnings = []
    for i, row in enumerate(rows):
        i += 1  # spreadsheet rows are one-indexed
        row_is_valid = True

        expected_length = 2
        if len(row) != expected_length:
            row_is_valid = False
            errors.append(_("Row {} should have {} columns but has {}").format(i, expected_length, len(row)))
        else:
            (old_path, new_path) = row

            if old_path not in old_paths_last_seen:
                row_is_valid = False
                errors.append(_("Path in row {} could not be found in application: <code>{}</code>").format(
                                i, old_path))
            elif old_paths_last_seen[old_path] is not None:
                # Duplicate old paths is an error: can't rename to two different new values
                row_is_valid = False
                errors.append(_("Path in row {} was already renamed in row {}: "
                                "<code>{}</code>").format(i, old_paths_last_seen[old_path], old_path))
            old_paths_last_seen[old_path] = i

            interpolated_new_path = interpolate_media_path(new_path)    # checks for jr://
            if interpolated_new_path != new_path:
                warnings.append(_("Path <code>{}</code> in row {} will be replaced with " \
                                  "<code>{}</code>").format(new_path, i, interpolated_new_path))
            else:
                # Duplicate new paths is a warning: will combine what were previously different items
                if new_path in new_paths_last_seen:
                    warnings.append(_("New path in row {} is already being used to rename row {}: "
                                      "<code>{}</code>").format(i, new_paths_last_seen[new_path], new_path))
            new_paths_last_seen[new_path] = i

        if row_is_valid:
            valid_count += 1

    return valid_count, errors, warnings
