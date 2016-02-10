from couchforms.models import XFormInstance
from corehq.util.quickcache import quickcache


def _sizeof_fmt(num):
    for x in ['bytes', 'KB', 'MB', 'GB', 'TB']:
        if num < 1024.0:
            return "%3.1f %s" % (num, x)
        num /= 1024.0


def get_attachment_size_by_domain(domain):
    return get_attachment_size_by_domain_app_id_xmlns(domain)


@quickcache(['domain', 'app_id', 'xmlns'], timeout=30)
def get_attachment_size_by_domain_app_id_xmlns(domain, app_id=None, xmlns=None):
    """
    :return: dict {
        (app_id, xmlns): size_of_attachments,
    }
    """
    startkey = [domain]
    if app_id:
        startkey += [app_id]
    if xmlns:
        startkey += [xmlns]

    view = XFormInstance.get_db().view(
        'attachments/attachments',
        startkey=startkey,
        endkey=startkey + [{}],
        group_level=3,
        reduce=True,
        group=True
    )
    # grouped key = [domain, app_id, xmlns]
    available_attachments = {(a['key'][1], a['key'][2]): _sizeof_fmt(a['value']) for a in view}
    return available_attachments
