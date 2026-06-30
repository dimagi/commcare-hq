"""
Post-submission validation checks that emit Sentry alerts when anomalies
are detected. These checks are observational only -- they never reject or
modify the submission.
"""
import sentry_sdk
from django.dispatch import receiver

from couchforms.signals import successful_form_received

IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif', '.heic', '.heif', '.bmp', '.webp')


@receiver(successful_form_received, dispatch_uid='check_image_attachments')
def check_image_attachments(sender, xform, **kwargs):
    """
    Alert when the set of image filenames referenced in form answers does
    not match the set of image attachments uploaded with the submission.

    See SAAS-19082 for more context.
    """
    image_attachments = {
        name for name in xform.attachments
        if name.lower().endswith(IMAGE_EXTENSIONS)
    }
    image_answers = _collect_image_references(xform.form_data)

    if image_attachments == image_answers:
        return

    mismatched = image_attachments.symmetric_difference(image_answers)
    with sentry_sdk.new_scope() as scope:
        scope.set_tag('domain', xform.domain)
        scope.set_tag('app_id', xform.app_id)
        scope.fingerprint = ['form-image-attachment-mismatch']
        scope.set_extra('form_id', xform.form_id)
        scope.set_extra('missing_attachments', sorted(image_answers - image_attachments))
        scope.set_extra('extra_attachments', sorted(image_attachments - image_answers))
        scope.set_extra('mismatched', sorted(mismatched))
        sentry_sdk.capture_message(
            'Form image answers do not match image attachments',
            level='warning',
        )


def _collect_image_references(form_data):
    """
    Return the set of leaf string values in ``form_data`` that look like
    image filenames.

    We identify image-capture answers by filename extension rather than by
    consulting the form definition (via app_id + xmlns). Fetching the form
    definition would let us locate image-capture questions precisely, but
    this signal handler runs for every successful submission, so the added
    DB/cache cost is not justified for an observational check.
    """
    found = set()
    _walk(form_data, found)
    return found


def _walk(node, found):
    if isinstance(node, dict):
        for value in node.values():
            _walk(value, found)
    elif isinstance(node, list):
        for value in node:
            _walk(value, found)
    elif isinstance(node, str):
        if node.lower().endswith(IMAGE_EXTENSIONS):
            found.add(node)
