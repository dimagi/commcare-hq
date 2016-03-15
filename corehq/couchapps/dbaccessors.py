from couchforms.models import XFormInstance
from corehq.util.quickcache import quickcache


def _sizeof_fmt(num):
    for x in ['bytes', 'KB', 'MB', 'GB', 'TB']:
        if num < 1024.0:
            return "%3.1f %s" % (num, x)
        num /= 1024.0


@quickcache(['domain', 'app_id', 'xmlns'], timeout=30)
def forms_have_multimedia(domain, app_id, xmlns):
    """
    :return: True if there is multimedia for forms with the given app_id and xmlns.
    """
    startkey = [domain, app_id, xmlns]
    rows = XFormInstance.get_db().view(
        'attachments/attachments',
        startkey=startkey,
        endkey=startkey + [{}],
        group_level=3,
        reduce=True,
        group=True
    )

    return rows.count() > 0
