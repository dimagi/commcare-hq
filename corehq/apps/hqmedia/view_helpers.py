from __future__ import absolute_import
from __future__ import unicode_literals

import six

from collections import defaultdict
from lxml import etree

from django.urls import reverse
from django.utils.translation import ugettext as _

from corehq.apps.app_manager.views.media_utils import interpolate_media_path


def download_multimedia_paths_rows(app, only_missing=False):
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
        if not only_missing or path not in app.multimedia_map:
            rows.append((_("Paths"), [path, ''] + [_readable_ref(r) for r in refs]))

    return rows


def validate_multimedia_paths_rows(app, rows):
    old_paths_last_seen = {i.path: None for i in app.all_media()}
    new_paths_last_seen = defaultdict(lambda: None)

    errors = []
    warnings = []
    for i, row in enumerate(rows):
        (old_path, new_path) = row

        if old_path not in old_paths_last_seen:
            errors.append(_("Path in row {} could not be found in application: "
                            "<code>{}</code>").format(i, old_path))
        elif old_path == new_path:
            errors.append(_("In row {}, old and new paths are both <code>{}</code>. Please provide "
                            "an updated path or remove this row").format(i, old_path))
        elif old_paths_last_seen[old_path] is not None:
            # Duplicate old paths is an error: can't rename to two different new values
            errors.append(_("Path in row {} was already renamed in row {}: "
                            "<code>{}</code>").format(i, old_paths_last_seen[old_path], old_path))
        old_paths_last_seen[old_path] = i

        interpolated_new_path = interpolate_media_path(new_path)    # checks for jr://
        if interpolated_new_path != new_path:
            warnings.append(_("Path <code>{}</code> in row {} was replaced with "
                              "<code>{}</code>").format(new_path, i, interpolated_new_path))
        else:
            # It's usually a bad idea to change file extensions, since the file itself isn't changing
            old_extension = old_path.split(".")[-1].lower()
            new_extension = new_path.split(".")[-1].lower()
            if old_extension != new_extension:
                warnings.append(_("File extension in row {} changed "
                                  "from {} to {}".format(i, old_extension, new_extension)))

            # Duplicate new paths is a warning: will combine what were previously different items
            if new_path in new_paths_last_seen:
                warnings.append(_("New path in row {} was already used to rename row {}: "
                                  "<code>{}</code>").format(i, new_paths_last_seen[new_path], new_path))
        new_paths_last_seen[new_path] = i

    return errors, warnings


def update_multimedia_paths(app, paths):
    # Update module and form references
    success_counts = defaultdict(lambda: 0)
    dirty_xform_ids = set()
    for old_path, new_path in six.iteritems(paths):
        for module in app.modules:
            success_counts[module.unique_id] += module.rename_media(old_path, new_path)
            for form in module.forms:
                update_count = form.rename_media(old_path, new_path)
                if update_count:
                    dirty_xform_ids.add(form.unique_id)
                    success_counts[form.unique_id] += update_count

    # Update any form xml that changed
    for module in app.modules:
        for form in module.forms:
            if form.unique_id in dirty_xform_ids:
                form.source = etree.tostring(form.memoized_xform().xml).decode('utf-8')

    # Update app's master map of multimedia
    for old_path, new_path in six.iteritems(paths):
        if old_path in app.multimedia_map:  # path will not be present if file is missing from app
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

    return successes
