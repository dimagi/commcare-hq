import logging
import requests

from cStringIO import StringIO
from jenkinsapi.jenkins import Jenkins

from corehq.apps.builds.models import CommCareBuild
from django.core.management.base import BaseCommand, CommandError


# supress requests library INFO logs
logging.getLogger("requests").setLevel(logging.WARNING)


class Command(BaseCommand):
    """
    This is an automated version of -
    https://github.com/dimagi/commcare-hq/tree/master/corehq/apps/builds#adding-commcare-j2me-builds-to-commcare-hq
    """
    help = "Interactively import a build from Jenkins build server."

    def handle(self, *args, **options):
        if not args:
            self.interactive_import()
        else:
            raise CommandError(self.help)

    def interactive_import(self):
        print "Pinging Jenkins build server. Pelase wait..."
        build_server = Jenkins("http://jenkins.dimagi.com")

        # let user choose one of ['commcare-mobile-2.21', 'commcare-mobile-2.22']
        jenkin_projects = build_server.keys()
        selected_project_key = None
        print "Jenkins has following projects. Please choose one"
        print [p for p in jenkin_projects if 'commcare-mobile' in p]
        while selected_project_key not in jenkin_projects:
            selected_project_key = raw_input("")

        print "Fetching build information for %s. Please wait..." % selected_project_key
        selected_project = build_server[selected_project_key]
        build_dict = selected_project.get_build_dict()
        builds_by_version_number = self._extract_version_numbers(build_dict)

        if not builds_by_version_number:
            print "Jenkins doesn't have any builds with a VERSION set. Go do it yourself at "\
                "http://jenkins.dimagi.com/job/%s", selected_project_key
            return

        selected_build_number = None
        print "Jenkins has following builds for %s. Choose a build-number to import" % selected_project_key
        print builds_by_version_number
        while selected_build_number not in builds_by_version_number.keys():
            selected_build_number = int(raw_input(""))

        # download and add the build
        version_number = builds_by_version_number.get(selected_build_number)
        build = selected_project.get_build_metadata(selected_build_number)
        artifacts = build.get_artifact_dict()
        artifacts_url = artifacts['artifacts.zip'].url

        print "Downloading and importing artifacts.zip. Please wait..."
        zip_file = requests.get(artifacts_url)
        self.add_build(StringIO(zip_file.content), version_number, selected_build_number)

    def add_build(self, build_path, version, build_number):
        try:
            CommCareBuild.create_from_zip(build_path, version, build_number)
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
        from StringIO import StringIO

        to_ret = {}
        count = 0
        for build_id in sorted(build_dict.keys()):
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
