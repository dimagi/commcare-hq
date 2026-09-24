"""Public webforms deep-link into a form via a session endpoint in a build's
suite. Each webform gets its own build, generated from the app's latest
released build with an endpoint added to the target form.

The generated build is "detached": its ``copy_of`` is a sentinel rather than
the canonical app id, so it is served by build id but stays out of the app's
build lineage (version history, latest build, releases, revert).
"""
from copy import deepcopy
from uuid import uuid4

from corehq.apps.app_manager.const import NON_BUILD_APP_KEYS
from corehq.apps.app_manager.dbaccessors import get_app, get_latest_released_app
from corehq.apps.app_manager.suite_xml.post_process.instances import (
    get_instance_names,
)
from corehq.blobs import get_blob_db

BUILD_COMMENT = "Automatically created for a public webform"
PUBLIC_WEBFORM_COPY_OF_SUFFIX = "__public_webform"


def create_public_webform_build(domain, app_id, form_unique_id):
    """Return ``(app_build_id, endpoint_id)`` for the target form.

    An endpoint is generated rather than reusing one the form may already
    have, so that a webform never depends on a build someone can delete.
    """
    released_build = get_latest_released_app(domain, app_id)
    endpoint_id = uuid4().hex
    new_build = _copy_for_build(released_build)
    new_build._force_session_endpoints = True
    new_build.get_form(form_unique_id).session_endpoint_id = endpoint_id
    _restrict_multimedia_to_form(new_build, form_unique_id)
    _restrict_reports_to_form(new_build, form_unique_id)
    new_build.profile.pop('custom_properties', None)
    new_build.convert_app_to_build(
        _public_webform_copy_of(released_build.copy_of),
        user_id=None,
        comment=BUILD_COMMENT,
    )
    new_build.copy_attachments(released_build)
    new_build._id = uuid4().hex
    new_build.create_build_files()
    new_build.save()
    return new_build._id, endpoint_id


def _restrict_multimedia_to_form(build, form_unique_id):
    """Drop every media path the target form does not reference.
    """
    form_paths = build.get_form(form_unique_id).all_media_paths()
    build.multimedia_map = {
        path: media
        for path, media in (build.multimedia_map or {}).items()
        if path in form_paths
    }


def _restrict_reports_to_form(build, form_unique_id):
    """Drop every mobile report the target form does not reference.

    A respondent restores the whole build's reports, and does so without a
    sync log, so the project's UCR sync interval never throttles it.
    """
    source = build.get_form(form_unique_id).source
    referenced = {
        name.split(':', 1)[1] for name in get_instance_names(source)
        if name.startswith(('commcare-reports:', 'commcare-reports-filters:'))
    }
    for module in build.get_report_modules():
        module.report_configs = [
            config for config in module.report_configs
            if config.instance_id in referenced
        ]


def delete_public_webform_build(domain, app_build_id):
    """Hard-delete a build that was generated explicitly for a public webform.
    """
    build = get_app(domain, app_build_id)
    assert _is_public_webform_build(build)
    blob_db = get_blob_db()
    build_files = blob_db.metadb.get_for_parent(build.get_id)
    build.delete()
    blob_db.bulk_delete(metas=build_files)


def _is_public_webform_build(build):
    return build.copy_of.endswith(PUBLIC_WEBFORM_COPY_OF_SUFFIX)


def _public_webform_copy_of(app_id):
    """A traceable, non-canonical ``copy_of``: keeps the doc a build (``copy_of``
    stays truthy) and out of the app's lineage, while recording its origin."""
    return f'{app_id}{PUBLIC_WEBFORM_COPY_OF_SUFFIX}'


def _copy_for_build(released_build):
    doc = deepcopy(released_build.to_json())
    for key in NON_BUILD_APP_KEYS:
        doc.pop(key, None)
    return type(released_build).wrap(doc)
