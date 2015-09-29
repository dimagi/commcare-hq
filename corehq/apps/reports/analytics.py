from collections import namedtuple
from corehq.util.couch import stale_ok
from corehq.util.quickcache import quickcache
from dimagi.utils.couch.database import get_db


FormAppInfo = namedtuple(
    'FormAppInfo',
    ['app_id', 'app_name', 'app_langs', 'is_user_registration',
     'module_name', 'form_name', 'app_deleted', 'duplicate'])


@quickcache(['domain', 'xmlns', 'app_id'], memoize_timeout=0, timeout=5 * 60)
def get_form_app_info(domain, xmlns, app_id):
    result = get_db().view(
        'exports_forms/by_xmlns',
        key=[domain, app_id, xmlns],
        group=True,
        stale=stale_ok(),
    ).one()
    if result:
        form_app_info = result['value']
        return FormAppInfo(
            app_id=form_app_info.get('app', {}).get('id'),
            app_name=form_app_info.get('app', {}).get('name'),
            app_langs=form_app_info.get('app', {}).get('langs'),
            is_user_registration=form_app_info.get('is_user_registration'),
            module_name=form_app_info.get('module', {}).get('name'),
            form_name=form_app_info.get('form', {}).get('name'),
            app_deleted=form_app_info.get('app_deleted'),
            duplicate=form_app_info.get('duplicate'),
        )
    else:
        return None
