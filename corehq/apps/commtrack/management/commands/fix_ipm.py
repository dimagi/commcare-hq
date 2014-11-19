from django.core.management.base import BaseCommand
from couchforms.models import XFormInstance
from dimagi.utils.couch.database import iter_docs
from corehq.apps.commtrack.models import SupplyPointCase


class Command(BaseCommand):
    startkey = ['ipm-senegal', 'by_type', 'XFormInstance']
    endkey = startkey + [{}]

    ids = [row['id'] for row in XFormInstance.get_db().view(
        "couchforms/all_submissions_by_domain",
        startkey=startkey,
        endkey=endkey,
        reduce=False
    )]

    to_save = []

    for doc in iter_docs(XFormInstance.get_db(), ids):
        if 'location_id' in doc['form'] and not doc['form']['location_id']:
            case = SupplyPointCase.get(doc['form']['case']['@case_id'])
            if case.type == 'supply-point':
                print 'updating'
                print 'case location_id:', case.location_id
                print 'from:', doc['form']['location_id']
                doc['form']['location_id'] = case.location_id
                print 'to:', doc['form']['location_id']
                to_save.append(doc)

        if len(to_save) > 500:
            XFormInstance.get_db().bulk_save(to_save)
            to_save = []

    if to_save:
        XFormInstance.get_db().bulk_save(to_save)
