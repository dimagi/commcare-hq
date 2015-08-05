from couchforms.util import create_xform, process_xform
from dimagi.utils.couch import LockManager, ReleaseOnError
from django.conf import settings


def create_and_save_xform(xml_string):
    assert getattr(settings, 'UNIT_TESTING', False)
    xform, lock = create_xform(xml_string, attachments={})
    with ReleaseOnError(lock):
        xform.save()
    return LockManager(xform.get_id, lock)


def post_xform_to_couch(instance, attachments=None, process=None,
                        domain='test-domain'):
    """
    create a new xform and releases the lock

    this is a testing entry point only and is not to be used in real code

    """
    assert getattr(settings, 'UNIT_TESTING', False)
    if not process:
        def process(xform):
            xform.domain = domain
    xform_lock = process_xform(instance, attachments=attachments,
                               process=process, domain=domain)
    with xform_lock as xforms:
        for xform in xforms:
            xform.save()
        return xforms[0]
