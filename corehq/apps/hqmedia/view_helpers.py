from __future__ import absolute_import
from __future__ import unicode_literals

import six

from collections import defaultdict
from lxml import etree

from django.urls import reverse
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

    errors = []
    warnings = []
    for i, row in enumerate(rows):
        i += 1  # spreadsheet rows are one-indexed

        expected_length = 2
        if len(row) != expected_length:
            errors.append(_("Row {} should have {} columns but has {}").format(i, expected_length, len(row)))
        else:
            (old_path, new_path) = row

            if old_path not in old_paths_last_seen:
                errors.append(_("Path in row {} could not be found in application: "
                                "<code>{}</code>").format(i, old_path))
            elif old_paths_last_seen[old_path] is not None:
                # Duplicate old paths is an error: can't rename to two different new values
                errors.append(_("Path in row {} was already renamed in row {}: "
                                "<code>{}</code>").format(i, old_paths_last_seen[old_path], old_path))
            old_paths_last_seen[old_path] = i

            interpolated_new_path = interpolate_media_path(new_path)    # checks for jr://
            if interpolated_new_path != new_path:
                warnings.append(_("Path <code>{}</code> in row {} will be replaced with "
                                  "<code>{}</code>").format(new_path, i, interpolated_new_path))
            else:
                # Duplicate new paths is a warning: will combine what were previously different items
                if new_path in new_paths_last_seen:
                    warnings.append(_("New path in row {} is already being used to rename row {}: "
                                      "<code>{}</code>").format(i, new_paths_last_seen[new_path], new_path))
            new_paths_last_seen[new_path] = i

    return errors, warnings


def update_multimedia_paths(app, paths):
    # Update module and form references
    success_counts = defaultdict(lambda: 0)
    xforms_by_id = defaultdict(lambda: None)    # cache forms rather than parsing repeatedly
    dirty_xform_ids = set()
    for old_path, new_path in six.iteritems(paths):
        for module in app.modules:
            success_counts[module.unique_id] += module.rename_media(old_path, new_path)
            if module.case_list_form.form_id:
                success_counts[module.unique_id] += module.case_list_form.rename_media(old_path, new_path)
            if hasattr(module, 'case_list') and module.case_list.show:
                success_counts[module.unique_id] += module.case_list.rename_media(old_path, new_path)
            for name, details, display in module.get_details():
                # Case list lookup
                if display and details.display == 'short' and details.lookup_enabled and details.lookup_image:
                    if details.lookup_image == old_path:
                        details.lookup_image = new_path
                        success_counts[module.unique_id] += 1

                # Icons in case details
                for column in details.get_columns():
                    if column.format == 'enum-image':
                        for map_item in column.enum:
                            for lang, icon in six.iteritems(map_item.value):
                                if icon == old_path:
                                    map_item.value[lang] = new_path
                                    success_counts[module.unique_id] += 1
            for form in module.forms:
                success_counts[form.unique_id] += form.rename_media(old_path, new_path)
                if not xforms_by_id[form.unique_id]:
                    xforms_by_id[form.unique_id] = form.wrapped_xform()
                update_count = xforms_by_id[form.unique_id].rename_media(old_path, new_path)
                success_counts[form.unique_id] += update_count
                if update_count:
                    dirty_xform_ids.add(form.unique_id)

    # Update any form xml that changed
    for module in app.modules:
        for form in module.forms:
            if form.unique_id in dirty_xform_ids:
                form.source = etree.tostring(xforms_by_id[form.unique_id].xml).decode('utf-8')

    # Update app's master map of multimedia
    for old_path, new_path in six.iteritems(paths):
        app.multimedia_map.update({
            new_path: app.multimedia_map[old_path],
        })

    # Put together success messages
    successes = []
    for module in app.modules:
        if success_counts[module.unique_id]:
            successes.append(_("{} item(s) updated in <a href='{}' target='_blank'>{}</a>").format(
                             success_counts[module.unique_id],
                             reverse("view_module", args=[app.domain, app.id, module.unique_id]),
                             module.default_name()))
        for form in module.forms:
            if success_counts[form.unique_id]:
                successes.append(_("{} item(s) updated in <a href='{}' target='_blank'>{}</a>").format(
                                 success_counts[form.unique_id],
                                 reverse("view_form", args=[app.domain, app.id, form.unique_id]),
                                 "{} > {}".format(module.default_name(), form.default_name())))
