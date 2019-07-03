from __future__ import absolute_import
from __future__ import unicode_literals

import six
import sys
from io import open
from celery.task import task

from corehq.apps.app_manager.dbaccessors import get_build_doc_by_version
from corehq.apps.hqmedia.tasks import create_files_for_ccz
from corehq.apps.app_manager.dbaccessors import wrap_app
from custom.icds.models import HostedCCZ


@task
def setup_ccz_file_for_hosting(hosted_ccz_id):
    try:
        hosted_ccz = HostedCCZ.objects.get(pk=hosted_ccz_id)
    except HostedCCZ.DoesNotExist:
        return
    version = hosted_ccz.version
    ccz_utility = hosted_ccz.utility
    # set up the file if not already present
    if not ccz_utility.file_exists():
        # profile_id should be None and not any other false value
        profile_id = hosted_ccz.profile_id or None
        build = wrap_app(get_build_doc_by_version(hosted_ccz.domain, hosted_ccz.app_id, version))
        ccz_file = create_files_for_ccz(build, profile_id)
        try:
            with open(ccz_file, 'rb') as ccz:
                ccz_utility.store_file_in_blobdb(ccz, name=hosted_ccz.file_name)
        except:
            exc = sys.exc_info()
            # delete the file from blob db if it was added but later failed
            hosted_ccz.delete_ccz()
            six.reraise(*exc)
