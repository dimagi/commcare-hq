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
    old_path_counts = {i.path: 0 for i in app.all_media()}
    new_path_counts = defaultdict(lambda: 0)

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

            if old_path not in old_path_counts:
                row_is_valid = False
                errors.append(_("Path in row {} could not be found in application: <code>{}</code>").format(
                                i, old_path))
            else:
                old_path_counts[old_path] += 1

            interpolated_new_path = interpolate_media_path(new_path)    # checks for jr://
            if interpolated_new_path != new_path:
                warnings.append(_("Badly formatted path <code>{}</code> in row {} will be replaced with " \
                                  "<code>{}</code>").format(new_path, i, interpolated_new_path))
            else:
                new_path_counts[new_path] += 1

        if row_is_valid:
            valid_count += 1

    # Duplicate old paths is an error: can't rename to two different new values
    for old_path, count in six.iteritems(old_path_counts):
        if count > 1:
            errors.append(_("Old path <code>{}</code> appears {} times in file.").format(old_path, count))

    # Duplicate new paths is a warning: will combine what were previously different items
    for new_path, count in six.iteritems(new_path_counts):
        if count > 1:
            warnings.append(_("New path <code>{}</code> appears {} times in file.").format(new_path, count))

    return valid_count, errors, warnings
