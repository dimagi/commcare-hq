from urllib.parse import quote, urljoin

from django.urls import reverse

from looseversion import LooseVersion

from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager.exceptions import MediaResourceError
from corehq.apps.app_manager.suite_xml.features.scheduler import (
    SchedulerFixtureContributor,
)
from corehq.apps.app_manager.suite_xml.post_process.endpoints import (
    EndpointsHelper,
)
from corehq.apps.app_manager.suite_xml.post_process.instances import (
    InstancesHelper,
)
from corehq.apps.app_manager.suite_xml.post_process.menu import (
    GridMenuHelper,
    RootMenuAssertionsHelper,
)
from corehq.apps.app_manager.suite_xml.post_process.remote_requests import (
    RemoteRequestsHelper,
)
from corehq.apps.app_manager.suite_xml.post_process.resources import (
    ResourceOverrideHelper,
)
from corehq.apps.app_manager.suite_xml.post_process.workflow import (
    WorkflowHelper,
)
from corehq.apps.app_manager.suite_xml.sections.details import (
    DetailContributor,
)
from corehq.apps.app_manager.suite_xml.sections.entries import (
    EntriesContributor,
)
from corehq.apps.app_manager.suite_xml.sections.fixtures import (
    FixtureContributor,
)
from corehq.apps.app_manager.suite_xml.sections.menus import MenuContributor
from corehq.apps.app_manager.suite_xml.sections.resources import (
    FormResourceContributor,
    LocaleResourceContributor,
    PracticeUserRestoreContributor,
)
from corehq.apps.app_manager.suite_xml.xml_models import (
    LocalizedMenu,
    MediaResource,
    Suite,
    Text,
)
from corehq.apps.app_manager.util import split_path
from corehq.apps.hqmedia.models import HQMediaMapItem


class SuiteGenerator(object):
    descriptor = "Suite File"

    def __init__(self, app, build_profile_id=None):
        self.app = app
        self.modules = list(app.get_modules())
        self.suite = Suite(version=self.app.version, descriptor=self.descriptor)
        self.build_profile_id = build_profile_id

    def add_section(self, contributor_cls):
        contributor = contributor_cls(self.suite, self.app, self.modules, self.build_profile_id)
        section = contributor.section_name
        section_elements = contributor.get_section_elements()
        getattr(self.suite, section).extend(section_elements)
        return section_elements

    def generate_suite(self):
        # Note: the order in which things happen in this function matters

        self.add_section(FormResourceContributor)
        self.add_section(LocaleResourceContributor)
        detail_section_elements = self.add_section(DetailContributor)

        if self.app.supports_practice_users and self.app.get_practice_user(self.build_profile_id):
            self.add_section(PracticeUserRestoreContributor)

        # by module
        entries = EntriesContributor(self.suite, self.app, self.modules, self.build_profile_id)
        menus = MenuContributor(self.suite, self.app, self.modules, self.build_profile_id)

        if any(module.is_training_module for module in self.modules):
            training_menu = LocalizedMenu(id='training-root')
            training_menu.text = Text(locale_id=id_strings.training_module_locale())
        else:
            training_menu = None

        for module in self.modules:
            self.suite.entries.extend(entries.get_module_contributions(module))

            self.suite.menus.extend(
                menus.get_module_contributions(module, training_menu)
            )

        if training_menu:
            self.suite.menus.append(training_menu)

        self.add_section(FixtureContributor)
        self.add_section(SchedulerFixtureContributor)

        RemoteRequestsHelper(self.suite, self.app, self.modules).update_suite(detail_section_elements)

        if self.app.supports_session_endpoints:
            EndpointsHelper(self.suite, self.app, self.modules).update_suite()
        if self.app.enable_post_form_workflow:
            WorkflowHelper(self.suite, self.app, self.modules).update_suite()
        if self.app.use_grid_menus:
            GridMenuHelper(self.suite, self.app, self.modules).update_suite()
        if self.app.custom_assertions:
            RootMenuAssertionsHelper(self.suite, self.app, self.modules).update_suite()

        InstancesHelper(self.suite, self.app, self.modules).update_suite()
        ResourceOverrideHelper(self.suite, self.app, self.modules).update_suite()
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
        multimedia_map = self.app.multimedia_map_for_build(build_profile=self.build_profile, remove_unused=True)
        lazy_load_preference = self.app.profile.get('properties', {}).get('lazy-load-video-files')
        for path, m in sorted(list(multimedia_map.items()), key=lambda item: item[0]):
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

            load_lazily = (lazy_load_preference == 'true' and m.media_type == "CommCareVideo")
            if not getattr(m, 'unique_id', None):
                # lazy migration for adding unique_id to map_item
                m.unique_id = HQMediaMapItem.gen_unique_id(m.multimedia_id, unchanged_path)

            descriptor = None
            if self.app.build_version and self.app.build_version >= LooseVersion('2.9'):
                type_mapping = {"CommCareImage": "Image",
                                "CommCareAudio": "Audio",
                                "CommCareVideo": "Video",
                                "CommCareMultimedia": "Text"}
                descriptor = "{filetype} File: {name}".format(
                    filetype=type_mapping.get(m.media_type, "Media"),
                    name=name
                )

            hqmedia_download_url = reverse(
                'hqmedia_download',
                args=[m.media_type, m.multimedia_id]
            ) + quote(name)
            yield MediaResource(
                id=id_strings.media_resource(m.unique_id, name),
                path=install_path,
                version=m.version,
                descriptor=descriptor,
                lazy=load_lazily,
                local=(local_path
                       if self.app.enable_local_resource
                       else None),
                remote=urljoin(self.app.url_base, hqmedia_download_url)
            )
