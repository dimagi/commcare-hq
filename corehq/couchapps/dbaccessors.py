from couchforms.models import XFormInstance
from corehq.util.quickcache import quickcache


def _sizeof_fmt(num):
    for x in ['bytes', 'KB', 'MB', 'GB', 'TB']:
        if num < 1024.0:
            return "%3.1f %s" % (num, x)
        num /= 1024.0


@quickcache(['domain'], timeout=30)
def get_attachment_size_by_domain(domain):
    """
    :return: dict {
        (app_id, xmlns): size_of_attachments,
    }
    """
    startkey = [domain]
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
