from collections import namedtuple
import json
from optparse import make_option

from django.core.management.base import BaseCommand

from couchforms.models import XFormInstance
from corehq.apps.app_manager.models import Application, RemoteApp
from corehq.apps.hqmedia.models import CommCareMultimedia

BlobInfo = namedtuple('BlobInfo', ['type', 'id', 'external_blob_ids'])


class Command(BaseCommand):
    help = "Command to migrate a domain's attachemnts in the blobdb to a new blobdb"
    args = '<domain>'
    option_list = BaseCommand.option_list + ()

    def handle(self, *args, **options):
        domain = args[0]
        blobs_to_copy = []
        blobs_to_copy.extend(get_saved_exports_blobs(domain))
        blobs_to_copy.extend(get_applications_blobs(domain))
        blobs_to_copy.extend(get_multimedia_blobs(domain))
        blobs_to_copy.extend(get_xforms_blobs(domain))
        with open('test.jsonl', 'w') as f:
            for doc in blobs_to_copy:
                f.write(json.dumps(doc._asdict()))
                f.write('\n')


def get_saved_exports_blobs(domain):
    # I think that this is only for caching exports, so not implementing
    return []


def get_applications_blobs(domain):
    apps = []
    apps.extend(Application.get_db().view(
        'by_domain_doc_type_date/view',
        startkey=[domain, 'Application', None],
        endkey=[domain, 'Application', None, {}],
        include_docs=True,
        reduce=False,
    ).all())
    apps.extend(Application.get_db().view(
        'by_domain_doc_type_date/view',
        startkey=[domain, 'Application-Deleted', None],
        endkey=[domain, 'Application-Deleted', None, {}],
        include_docs=True,
        reduce=False,
    ).all())
    apps.extend(RemoteApp.get_db().view(
        'by_domain_doc_type_date/view',
        startkey=[domain, 'RemoteApplication', None],
        endkey=[domain, 'RemoteApplication', None, {}],
        include_docs=True,
        reduce=False,
    ).all())
    apps.extend(RemoteApp.get_db().view(
        'by_domain_doc_type_date/view',
        startkey=[domain, 'RemoteApplication-Deleted', None],
        endkey=[domain, 'RemoteApplication-Deleted', None, {}],
        include_docs=True,
        reduce=False,
    ).all())

    return _format_return_value(apps)


def get_multimedia_blobs(domain):
    media = CommCareMultimedia.get_db().view(
        'hqmedia/by_domain',
        startkey=[domain],
        endkey=[domain, {}],
        include_docs=True,
        reduce=False,
    ).all()
    return _format_return_value(media)


def get_xforms_blobs(domain):
    xforms = XFormInstance.get_db().view(
        'couchforms/all_submissions_by_domain',
        startkey=[domain],
        endkey=[domain, {}],
        include_docs=True,
        reduce=False,
    ).all()
    return _format_return_value(xforms)


def _format_return_value(docs):
    return [
        BlobInfo(doc['doc']['doc_type'], doc['id'],
            [blob['id'] for blob in doc['doc']['external_blobs'].values()]
        )
        for doc in docs
    ]
