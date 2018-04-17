from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
import logging
import requests
from io import BytesIO, StringIO

from jenkinsapi.jenkins import Jenkins

from corehq.apps.builds.models import CommCareBuild
from django.core.management.base import BaseCommand, CommandError
from memoized import memoized
from six.moves import input
import six


class Command(BaseCommand):
    """
    This is an automated version of -
    https://github.com/dimagi/commcare-hq/tree/master/corehq/apps/builds#adding-commcare-j2me-builds-to-commcare-hq
    """
    help = "Interactively import a build from Jenkins build server."

    def handle(self, **options):
        self.interactive_import()

    def interactive_import(self):

        # supress requests library INFO logs
        logging.getLogger("requests").setLevel(logging.WARNING)

        # let user chose a project from the list ['commcare-mobile-2.21', ...]
        selected_project_key = None
        print("Jenkins has following projects. Please choose one (to end enter END)")
        print([p for p in self.jenkin_projects if 'commcare-mobile' in p])
        while selected_project_key not in self.jenkin_projects:
            selected_project_key = input("")
            if selected_project_key.lower() == 'end':
                return

        print("Fetching build information for %s. Please wait..." % selected_project_key)
        selected_project = self.build_server[selected_project_key]
        build_dict = selected_project.get_build_dict()
        builds_by_version_number = self._extract_version_numbers(build_dict)

        if not builds_by_version_number:
            abort = input("This project doesn't have any builds that has a VERSION set. Do you want"
                              " to chose another project  (Yes) or abort (No).")
            if abort.lower() == 'no':
                print("Builds URL http://jenkins.dimagi.com/job/", selected_project_key)
                return
            else:
                return self.interactive_import()
            return

        selected_build_number = None
        print("Jenkins has following builds for %s. Choose a build-number to import (to end enter 0)" \
              % selected_project_key)
        print(builds_by_version_number)
        while selected_build_number not in builds_by_version_number:
            if selected_build_number == 0:
                return
            selected_build_number = int(input(""))

        # download and add the build
        print("Downloading and importing artifacts.zip. Please wait...")
        version_number = builds_by_version_number.get(selected_build_number)
        build = selected_project.get_build_metadata(selected_build_number)
        artifacts = build.get_artifact_dict()
        artifacts_url = artifacts['artifacts.zip'].url

        try:
            zip_file = requests.get(artifacts_url)
        except:
            print("Failed to fetch artifacts.zip at URL`")
            print(artifacts_url)
            return

        self.add_build(BytesIO(zip_file.content), version_number, selected_build_number)

    @property
    @memoized
    def jenkin_projects(self):
        print("Pinging Jenkins build server. Pelase wait...")
        return list(six.iterkeys(self.build_server))

    @property
    @memoized
    def build_server(self):
        return Jenkins("http://jenkins.dimagi.com")

    def add_build(self, builf_file, version, build_number):
        try:
            CommCareBuild.create_from_zip(builf_file, version, build_number)
        except Exception as e:
            raise CommandError("%s" % e)
        self.stdout.write('Build %s #%s created\n' % (version, build_number))
        self.stdout.write('You can see a list of builds at [your-server]/builds/')
        self.stdout.write(' and edit its label at [your-server]/builds/edit_menu\n')

    def _extract_version_numbers(self, build_dict, max_options=5):
        """
        - takes build_dict is of following format
            {352167: 'http://jenkins.dimagi.com/job/commcare-mobile-2.21/352167/',
             352366: 'http://jenkins.dimagi.com/job/commcare-mobile-2.21/352366/'}
        - sorts by the key and returns dict of following format with #items=max_options
            {352167: 2.19.1
             352366: 2.22.0}
        """
        from lxml import etree

        to_ret = {}
        count = 0
        for build_id in sorted(build_dict):
            if count > max_options:
                return to_ret
            # jenkinsapi has no support for plugins. Following is a very dirty way
            env_url = build_dict.get(build_id) + "/injectedEnvVars"
            envs = requests.get(env_url)
            tr = etree.parse(StringIO(envs.text), etree.HTMLParser())
            version = tr.xpath("//*[contains(text(),'VERSION')]/following-sibling::*")
            if not version:
                # some builds don't have VERSION set
                continue
            version = ''.join(version[0].itertext())
            to_ret[build_id] = version
            count = count + 1
        return to_ret
