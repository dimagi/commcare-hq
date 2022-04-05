import textwrap

from django.core.management.base import BaseCommand, CommandError

from github import Github

from corehq.apps.builds.models import (
    BuildMenuItem,
    BuildSpec,
    CommCareBuild,
    CommCareBuildConfig,
)


class Command(BaseCommand):
    help = textwrap.dedent("""
        Adds a commcare build, labeled with the version (x.y.z) Usage:
        "./manage.py add_commcare_build --latest" or
        "./manage.py add_commcare_build --version=2.53.0" see also
        https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/builds/README.rst
    """)

    def add_arguments(self, parser):
        parser.add_argument('build_args', nargs='*')
        parser.add_argument('--build_version')
        parser.add_argument(
            '-l',
            '--latest',
            action='store_true',
            help="add the latest CommCare build version from GitHub"
        )

    def handle(self, build_args, **options):
        if options['latest']:
            version = _get_latest_commcare_build_version()
            self._create_build_with_version(version)
        elif options['build_version']:
            self._create_build_with_version(options['build_version'])
        else:
            if len(build_args) == 3:
                build_path, version, build_number = build_args
                try:
                    CommCareBuild.create_from_zip(build_path, version, build_number)
                except Exception as e:
                    raise CommandError("%s" % e)
                self.stdout.write('Build %s #%s created\n' % (version, build_number))
                self.stdout.write('You can see a list of builds at [your-server]/builds/\n')
            else:
                raise CommandError("<build_path>, <version> or <build_number> not specified!")

    def _create_build_with_version(self, version):
        if any(build.version == version for build in CommCareBuild.all_builds()):
            self.stdout.write(f"A build for version {version} already exists. You're up-to-date!")
        else:
            CommCareBuild.create_without_artifacts(version, None)
            _update_commcare_build_menu(version)
            self.stdout.write(f"Added build for version {version}.")


def _get_latest_commcare_build_version():
    repo = Github().get_organization('dimagi').get_repo("commcare-android")
    latest_release_tag = repo.get_latest_release().tag_name

    return latest_release_tag.split('commcare_')[1]


def _update_commcare_build_menu(version):
    build_config_doc = CommCareBuildConfig.fetch()
    _add_build_menu_item(build_config_doc, version)
    _update_default_build_spec_to_version(build_config_doc, version)

    build_config_doc.save()
    CommCareBuildConfig.clear_local_cache()


def _add_build_menu_item(build_config, version):
    build_menu_items = build_config.menu

    build = BuildSpec(version=version, latest=True)
    build_menu_item = BuildMenuItem(build=build, label="CommCare {}".format(version), j2me_enabled=False)
    build_menu_items.append(build_menu_item)


def _update_default_build_spec_to_version(build_config, version):
    major_version = version[0]
    defaults = build_config.defaults

    major_default_build_spec = next(
        (default for default in defaults if default.version.startswith(major_version)),
        None
    )

    if major_default_build_spec and major_default_build_spec.version != version:
        major_default_build_spec.version = version
