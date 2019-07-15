from __future__ import absolute_import
from __future__ import unicode_literals

import six
import sys
from io import open
from celery.task import task
from django.template.defaultfilters import linebreaksbr

from corehq.apps.app_manager.dbaccessors import get_build_doc_by_version
from corehq.apps.hqmedia.tasks import create_files_for_ccz
from corehq.apps.app_manager.dbaccessors import wrap_app
from custom.icds.models import HostedCCZ
from corehq.apps.hqwebapp.tasks import send_html_email_async


@task
def setup_ccz_file_for_hosting(hosted_ccz_id, user_email=None):
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
        try:
            ccz_file = create_files_for_ccz(build, profile_id,
                                            download_targeted_version=bool(build.commcare_flavor))
            with open(ccz_file, 'rb') as ccz:
                ccz_utility.store_file_in_blobdb(ccz, name=hosted_ccz.file_name)
        except:
            exc = sys.exc_info()
            if user_email:
                _notify_failure_to_user(hosted_ccz, build, user_email)
            # delete the file from blob db if it was added but later failed
            hosted_ccz.delete_ccz()
            six.reraise(*exc)


def _notify_failure_to_user(hosted_ccz, build, user_email):
    build_profile = hosted_ccz.build_profile
    profile_name = build_profile.get('name') if build_profile else None
    content = "Hi,\n"\
              "CCZ could not be created for the following request:\n" \
              "App: {app}\n" \
              "Version: {version}\n" \
              "Profile: {profile}\n" \
              "Link: {link}" \
              "".format(app=build.name, version=hosted_ccz.version, profile=profile_name,
                        link=hosted_ccz.link.identifier)
    send_html_email_async.delay(
        "CCZ Hosting setup failed for app {app} in project {domain}".format(
            app=build.name,
            domain=hosted_ccz.domain,
        ),
        user_email,
        linebreaksbr(content)
    )
