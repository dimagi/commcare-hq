from __future__ import absolute_import
from __future__ import unicode_literals
import six.moves.urllib.request, six.moves.urllib.parse, six.moves.urllib.error

from django.urls import reverse

from corehq.apps.app_manager.exceptions import MediaResourceError
from corehq.apps.app_manager.suite_xml.post_process.menu import GridMenuHelper
from corehq.apps.app_manager.suite_xml.sections.details import DetailContributor
from corehq.apps.app_manager.suite_xml.sections.entries import EntriesContributor
from corehq.apps.app_manager.suite_xml.features.scheduler import SchedulerFixtureContributor
from corehq.apps.app_manager.suite_xml.sections.fixtures import FixtureContributor
from corehq.apps.app_manager.suite_xml.post_process.instances import EntryInstances
from corehq.apps.app_manager.suite_xml.sections.menus import MenuContributor
from corehq.apps.app_manager.suite_xml.sections.resources import(
    FormResourceContributor,
    LocaleResourceContributor,
    PracticeUserRestoreContributor,
)
from corehq.apps.app_manager.suite_xml.post_process.workflow import WorkflowHelper
from corehq.apps.app_manager.suite_xml.sections.remote_requests import RemoteRequestContributor
from corehq.apps.app_manager.suite_xml.xml_models import Suite, MediaResource
from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager.util import split_path
from corehq.apps.hqmedia.models import HQMediaMapItem


class SuiteGenerator(object):
    descriptor = "Suite File"

    def __init__(self, app, build_profile_id=None):
        self.app = app
        self.modules = list(app.get_modules())
        self.suite = Suite(version=self.app.version, descriptor=self.descriptor)
        self.build_profile_id = build_profile_id

    def _add_sections(self, contributors):
        for contributor in contributors:
            section = contributor.section_name
            getattr(self.suite, section).extend(
                contributor.get_section_elements()
            )

    def generate_suite(self):
        # Note: the order in which things happen in this function matters

        self._add_sections([
            FormResourceContributor(self.suite, self.app, self.modules, self.build_profile_id),
            LocaleResourceContributor(self.suite, self.app, self.modules, self.build_profile_id),
            DetailContributor(self.suite, self.app, self.modules, self.build_profile_id),
        ])

        if self.app.supports_practice_users and self.app.get_practice_user(self.build_profile_id):
            self._add_sections([
                PracticeUserRestoreContributor(self.suite, self.app, self.modules, self.build_profile_id)
            ])

        # by module
        entries = EntriesContributor(self.suite, self.app, self.modules)
        menus = MenuContributor(self.suite, self.app, self.modules)
        remote_requests = RemoteRequestContributor(self.suite, self.app, self.modules)
        for module in self.modules:
            self.suite.entries.extend(entries.get_module_contributions(module))

            self.suite.menus.extend(
                menus.get_module_contributions(module)
            )

            self.suite.remote_requests.extend(remote_requests.get_module_contributions(module))

        self._add_sections([
            FixtureContributor(self.suite, self.app, self.modules),
            SchedulerFixtureContributor(self.suite, self.app, self.modules),
        ])

        # post process
        if self.app.enable_post_form_workflow:
            WorkflowHelper(self.suite, self.app, self.modules).update_suite()
        if self.app.use_grid_menus:
            GridMenuHelper(self.suite, self.app, self.modules).update_suite()

        EntryInstances(self.suite, self.app, self.modules).update_suite()
        return self.suite.serializeDocument(pretty=True)


class MediaSuiteGenerator(object):
    descriptor = "Media Suite File"

    def __init__(self, app, build_profile_id=None):
        self.app = app
        self.build_profile = app.build_profiles[build_profile_id] if build_profile_id else None
        self.suite = Suite(
            version=self.app.version,
            descriptor=self.descriptor,
        )

    def generate_suite(self):
        self.suite.media_resources.extend(self.media_resources)
        return self.suite.serializeDocument(pretty=True)

    @property
    def media_resources(self):
        PREFIX = 'jr://file/'
        # you have to call remove_unused_mappings
        # before iterating through multimedia_map
        self.app.remove_unused_mappings()
        if self.app.multimedia_map is None:
            self.app.multimedia_map = {}
        filter_multimedia = self.app.media_language_map and self.build_profile
        if filter_multimedia:
            media_list = []
            for lang in self.build_profile.langs:
                media_list += self.app.media_language_map[lang].media_refs
            requested_media = set(media_list)
        for path, m in sorted(list(self.app.multimedia_map.items()), key=lambda item: item[0]):
            if filter_multimedia and m.form_media and path not in requested_media:
                continue
            unchanged_path = path
            if path.startswith(PREFIX):
                path = path[len(PREFIX):]
            else:
                raise MediaResourceError('%s does not start with %s' % (path, PREFIX))
            path, name = split_path(path)
            # CommCare assumes jr://media/,
            # which is an alias to jr://file/commcare/media/
            # so we need to replace 'jr://file/' with '../../'
            # (this is a hack)
            install_path = '../../{}'.format(path)
            local_path = './{}/{}'.format(path, name)

            if not getattr(m, 'unique_id', None):
                # lazy migration for adding unique_id to map_item
                m.unique_id = HQMediaMapItem.gen_unique_id(m.multimedia_id, unchanged_path)

            descriptor = None
            if self.app.build_version >= '2.9':
                type_mapping = {"CommCareImage": "Image",
                                "CommCareAudio": "Audio",
                                "CommCareVideo": "Video",
                                "CommCareMultimedia": "Text"}
                descriptor = "{filetype} File: {name}".format(
                    filetype=type_mapping.get(m.media_type, "Media"),
                    name=name
                )

            yield MediaResource(
                id=id_strings.media_resource(m.unique_id, name),
                path=install_path,
                version=m.version,
                descriptor=descriptor,
                local=(local_path
                       if self.app.enable_local_resource
                       else None),
                remote=self.app.url_base + reverse(
                    'hqmedia_download',
                    args=[m.media_type, m.multimedia_id]
                ) + six.moves.urllib.parse.quote(name.encode('utf-8')) if name else name
            )
