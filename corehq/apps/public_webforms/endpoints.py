"""Create the session endpoint a public webform navigates to.

Public webforms deep-link into a form via a session endpoint in a build's
suite. Each webform gets its own build, generated from the app's latest
released build with an endpoint added to the target form.

The generated build is "detached": its ``copy_of`` is a sentinel rather than
the canonical app id, so it is served by build id but stays out of the app's
build lineage (version history, latest build, releases, revert).
"""
from copy import deepcopy
from uuid import uuid4

from corehq.apps.app_manager.dbaccessors import get_latest_released_app

BUILD_COMMENT = "Automatically created for a public webform"
STRIPPED_BUILD_KEYS = (
    '_id', '_rev', '_attachments', 'external_blobs',
    'short_odk_url', 'short_odk_media_url', 'recipients',
)


def create_public_webform_endpoint(domain, app_id, form_unique_id):
    """Return ``(app_build_id, endpoint_id)`` for the target form.

    An endpoint is generated rather than reusing one the form may already
    have, so that a webform never depends on a build someone can delete.
    """
    released_build = get_latest_released_app(domain, app_id)
    endpoint_id = uuid4().hex
    new_build = _copy_for_build(released_build)
    new_build._force_session_endpoints = True
    new_build.get_form(form_unique_id).session_endpoint_id = endpoint_id
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


def _public_webform_copy_of(app_id):
    """A traceable, non-canonical ``copy_of``: keeps the doc a build (``copy_of``
    stays truthy) and out of the app's lineage, while recording its origin."""
    return f'{app_id}__public_webform'


def _copy_for_build(released_build):
    doc = deepcopy(released_build.to_json())
    for key in STRIPPED_BUILD_KEYS:
        doc.pop(key, None)
    return type(released_build).wrap(doc)
