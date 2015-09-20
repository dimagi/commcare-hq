import urllib

from django.core.urlresolvers import reverse

from corehq.apps.app_manager.exceptions import MediaResourceError
from corehq.apps.app_manager.suite_xml.sections.details import DetailContributor, DetailsHelper
from corehq.apps.app_manager.suite_xml.sections.entries import EntriesContributor
from corehq.apps.app_manager.suite_xml.features.careplan import CareplanMenuContributor
from corehq.apps.app_manager.suite_xml.features.scheduler import SchedulerContributor
from corehq.apps.app_manager.suite_xml.sections.fixtures import FixtureContributor
from corehq.apps.app_manager.suite_xml.post_process.instances import EntryInstances
from corehq.apps.app_manager.suite_xml.sections.menus import MenuContributor
from corehq.apps.app_manager.suite_xml.sections.resources import FormResourceContributor, LocaleResourceContributor
from corehq.apps.app_manager.suite_xml.post_process.workflow import WorkflowHelper
from corehq.apps.app_manager.suite_xml.xml_models import Suite, MediaResource
from corehq.apps.app_manager import id_strings
from corehq.apps.app_manager.util import split_path
from corehq.apps.hqmedia.models import HQMediaMapItem
from dimagi.utils.web import get_url_base


class SuiteGenerator(object):
    descriptor = u"Suite File"

    def __init__(self, app):
        self.app = app
        self.modules = list(app.get_modules())
        self.details_helper = DetailsHelper(self.app, self.modules)
        self.suite = Suite(
            version=self.app.version,
            descriptor=self.descriptor,
        )

    def generate_suite(self):
        FormResourceContributor(self.suite, self.app, self.modules).contribute()
        LocaleResourceContributor(self.suite, self.app, self.modules).contribute()
        DetailContributor(self.suite, self.app, self.modules).contribute()

        entries = EntriesContributor(self.suite, self.app, self.modules)
        for module in self.modules:
            self.suite.entries.extend(entries.get_module_contributions(module))

        menus = MenuContributor(self.suite, self.app, self.modules)
        careplan_menus = CareplanMenuContributor(self.suite, self.app, self.modules)
        for module in self.modules:
            self.suite.menus.extend(
                careplan_menus.get_module_contributions(module)
            )
            self.suite.menus.extend(
                menus.get_module_contributions(module)
            )

        self.suite.fixtures.extend(
            FixtureContributor(self.suite, self.app, self.modules).get_section_contributions(),
        )
        self.suite.fixtures.extend(
            SchedulerContributor(self.suite, self.app, self.modules).fixtures()
        )

        if self.app.enable_post_form_workflow:
            WorkflowHelper(self.suite, self.app, self.modules).add_form_workflow()

        EntryInstances(self.suite, self.app, self.modules).contribute()
        return self.suite.serializeDocument(pretty=True)


class MediaSuiteGenerator(object):
    descriptor = u"Media Suite File"

    def __init__(self, app):
        self.app = app
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
        for path, m in self.app.multimedia_map.items():
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
            install_path = u'../../{}'.format(path)
            local_path = u'./{}/{}'.format(path, name)

            if not getattr(m, 'unique_id', None):
                # lazy migration for adding unique_id to map_item
                m.unique_id = HQMediaMapItem.gen_unique_id(m.multimedia_id, unchanged_path)

            descriptor = None
            if self.app.build_version >= '2.9':
                type_mapping = {"CommCareImage": "Image",
                                "CommCareAudio": "Audio",
                                "CommCareVideo": "Video",
                                "CommCareMultimedia": "Text"}
                descriptor = u"{filetype} File: {name}".format(
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
                remote=get_url_base() + reverse(
                    'hqmedia_download',
                    args=[m.media_type, m.multimedia_id]
                ) + urllib.quote(name.encode('utf-8')) if name else name
            )
