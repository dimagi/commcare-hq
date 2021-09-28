import logging
from datetime import datetime
import time

from corehq.blobs import get_blob_db
from corehq.apps.app_manager.dbaccessors import get_app

'''
Temporary script used to periodically poll the internal state of an application
form to catch changes. Refer to https://dimagi-dev.atlassian.net/browse/SAAS-11820
TODO: Remove when case closed.
'''


def form_blob(app_id, form_key):
    db = get_blob_db()
    meta = db.metadb.get(parent_id=app_id, key=form_key)
    with meta.open() as fn:
        source = fn.read()
        return source


def app_details(domain, app_id, form_key):
    app = get_app(domain, app_id)
    return {
        'form_key': app.external_blobs[form_key + '.xml'].key
    }


def run(domain, app_id, form_key, dir="form_blobs", interval_in_seconds=600, log_name=None):
    logger = logging.getLogger('scripts.tmp-disappearing-form-poller')
    if log_name:
        fh = logging.FileHandler('tmp.log')
        formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s')
        fh.setFormatter(formatter)
        logger.addHandler(fh)

    last_form_blob = None
    while True:
        # get app details and blob
        app_deets = app_details(domain, app_id, form_key)
        app_form_key = app_deets['form_key']
        cur_form_blob = form_blob(app_id, app_form_key)

        # Compare blob against old
        changed = last_form_blob != cur_form_blob

        logger.info(f'form key: {app_form_key}. Blob {"changed" if changed and last_form_blob else "unchanged"}.')

        # Print to file if blob changed
        if changed:
            date_str = datetime.now().isoformat()
            file_name = f'{dir}/{date_str}-{app_form_key}-{"CHANGED" if last_form_blob else ""}.xml'
            with open(file_name, 'wb') as fn:
                fn.write(cur_form_blob)

        last_form_blob = cur_form_blob
        time.sleep(int(interval_in_seconds))
