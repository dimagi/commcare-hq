import random
from github import Github

from django.core.management.base import BaseCommand, CommandError
from corehq.apps.builds.models import CommCareBuild, CommCareBuildConfig, BuildMenuItem, BuildSpec


class Command(BaseCommand):
    help = ('Adds a commcare build, labeled with the version (x.y.z) and build_number (an incrementing integer)\n'
            'to get started see https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/builds/README.md')

    def add_arguments(self, parser):
        parser.add_argument('build_path', nargs='?')
        parser.add_argument('version', nargs='?')
        parser.add_argument('build_number', nargs='?')
        parser.add_argument(
            '-l',
            '--latest',
            action='store_true',
            help="add the latest remote CommCare build version"
        )

    def handle(self, build_path, version, build_number, **options):
        if options.get('latest'):
            _create_build_from_latest_remote_version()
        else:
            if build_path and version and build_number:
                try:
                    build_number = int(build_number)
                except ValueError:
                    raise CommandError("Build Number %r is not an integer" % build_number)

                try:
                    CommCareBuild.create_from_zip(build_path, version, build_number)
                except Exception as e:
                    raise CommandError("%s" % e)
                self.stdout.write('Build %s #%s created\n' % (version, build_number))
                self.stdout.write('You can see a list of builds at [your-server]/builds/\n')
            else:
                raise CommandError("<build_path>, <version> or <build_number> not specified!")


def _create_build_from_latest_remote_version():
    version = _get_latest_commcare_build_version()
    # arbitrary build_number
    build_number = random.randint(0, 100)

    CommCareBuild.create_without_artifacts(version, build_number)
    _update_commcare_build_menu(version, build_number)


def _get_latest_commcare_build_version():
    repo = Github().get_organization('dimagi').get_repo("commcare-android")
    latest_release_tag = repo.get_latest_release().tag_name

    return latest_release_tag.split('commcare_')[1]


def _update_commcare_build_menu(version, build_number):
    doc = CommCareBuildConfig.fetch()
    _add_build_menu_item(doc, version, build_number)
    _update_default_build_spec_to_version(doc, version)

    CommCareBuildConfig.get_db().save_doc(doc)
    CommCareBuildConfig.clear_local_cache()


def _add_build_menu_item(doc, version, build_number):
    build_menu_items = doc.menu

    build_menu_item = next(
        (build_item for build_item in build_menu_items if build_item.build.version == version),
        None
    )
    if build_menu_item is None:
        build = BuildSpec(version=version, build_number=build_number, latest=True)
        build_menu_item = BuildMenuItem(build=build, label="CommCare {}".format(version), j2me_enabled=False)
        build_menu_items.append(build_menu_item)


def _update_default_build_spec_to_version(doc, version):
    major_version = version[0]
    defaults = doc.defaults

    major_default_build_spec = next(
        (default for default in defaults if default.version.startswith(major_version)),
        None
    )

    if major_default_build_spec and major_default_build_spec.version != version:
        major_default_build_spec.version = version
