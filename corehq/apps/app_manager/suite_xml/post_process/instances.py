from __future__ import absolute_import
from __future__ import unicode_literals
from collections import defaultdict
import re
from django.utils.translation import ugettext as _

from corehq import toggles
from corehq.apps.app_manager.exceptions import DuplicateInstanceIdError
from corehq.apps.app_manager.suite_xml.contributors import PostProcessor
from corehq.apps.app_manager.suite_xml.xml_models import Instance
from memoized import memoized
import six


class EntryInstances(PostProcessor):

    def update_suite(self):
        for entry in self.suite.entries:
            self.add_entry_instances(entry)

    def add_entry_instances(self, entry):
        xpaths = self._get_all_xpaths_for_entry(entry)
        known_instances, unknown_instance_ids = get_all_instances_referenced_in_xpaths(self.app.domain, xpaths)
        custom_instances, unknown_instance_ids = self._get_custom_instances(
            entry,
            known_instances,
            unknown_instance_ids
        )
        all_instances = known_instances | custom_instances
        entry.require_instances(instances=all_instances, instance_ids=unknown_instance_ids)

    def _get_all_xpaths_for_entry(self, entry):
        relevance_by_menu, menu_by_command = self._get_menu_relevance_mapping()
        details_by_id = self._get_detail_mapping()
        detail_ids = set()
        xpaths = set()

        for datum in entry.datums:
            detail_ids.add(datum.detail_confirm)
            detail_ids.add(datum.detail_select)
            detail_ids.add(datum.detail_inline)
            detail_ids.add(datum.detail_persistent)
            xpaths.add(datum.nodeset)
            xpaths.add(datum.function)
        details = [details_by_id[detail_id] for detail_id in detail_ids if detail_id]

        entry_id = entry.command.id
        menu_id = menu_by_command[entry_id]
        relevances = relevance_by_menu[menu_id]
        xpaths.update(relevances)

        for detail in details:
            xpaths.update(detail.get_all_xpaths())
        for assertion in entry.assertions:
            xpaths.add(assertion.test)
        if entry.stack:
            for frame in entry.stack.frames:
                xpaths.add(frame.if_clause)
                if hasattr(frame, 'datums'):
                    for datum in frame.datums:
                        xpaths.add(datum.value)
        xpaths.discard(None)
        return xpaths

    @memoized
    def _get_detail_mapping(self):
        return {detail.id: detail for detail in self.suite.details}

    @memoized
    def _get_menu_relevance_mapping(self):
        relevance_by_menu = defaultdict(list)
        menu_by_command = {}
        for menu in self.suite.menus:
            for command in menu.commands:
                menu_by_command[command.id] = menu.id
                if command.relevant:
                    relevance_by_menu[menu.id].append(command.relevant)
            if menu.relevant:
                relevance_by_menu[menu.id].append(menu.relevant)

        return relevance_by_menu, menu_by_command

    def _get_custom_instances(self, entry, known_instances, required_instances):
        known_instance_ids = [instance.id for instance in known_instances]
        try:
            custom_instances = self._custom_instances_by_xmlns()[entry.form]
        except KeyError:
            custom_instances = []

        for instance in custom_instances:
            if instance.instance_id in known_instance_ids:
                raise DuplicateInstanceIdError(
                    _("Duplicate custom instance in {}: {}").format(entry.command.id, instance.instance_id))
            # Remove custom instances from required instances, but add them even if they aren't referenced anywhere
            required_instances.discard(instance.instance_id)
        return {
            Instance(id=instance.instance_id, src=instance.instance_path) for instance in custom_instances
        }, required_instances

    @memoized
    def _custom_instances_by_xmlns(self):
        return {form.xmlns: form.custom_instances for form in self.app.get_forms() if form.custom_instances}


def get_instance_factory(scheme):
    return get_instance_factory._factory_map.get(scheme, preset_instances)
get_instance_factory._factory_map = {}


class register_factory(object):

    def __init__(self, *schemes):
        self.schemes = schemes

    def __call__(self, fn):
        for scheme in self.schemes:
            get_instance_factory._factory_map[scheme] = fn
        return fn


INSTANCE_KWARGS_BY_ID = {
    'groups': dict(id='groups', src='jr://fixture/user-groups'),
    'reports': dict(id='reports', src='jr://fixture/commcare:reports'),
    'ledgerdb': dict(id='ledgerdb', src='jr://instance/ledgerdb'),
    'casedb': dict(id='casedb', src='jr://instance/casedb'),
    'commcaresession': dict(id='commcaresession', src='jr://instance/session'),
}


@register_factory(*list(INSTANCE_KWARGS_BY_ID.keys()))
def preset_instances(domain, instance_name):
    kwargs = INSTANCE_KWARGS_BY_ID.get(instance_name, None)
    if kwargs:
        return Instance(**kwargs)


@register_factory('item-list', 'schedule', 'indicators', 'commtrack')
@memoized
def generic_fixture_instances(domain, instance_name):
    return Instance(id=instance_name, src='jr://fixture/{}'.format(instance_name))


@register_factory('enikshay')
def enikshay_fixture_instances(domain, instance_name):
    if instance_name == 'enikshay:calendar' and toggles.CUSTOM_CALENDAR_FIXTURE.enabled(domain):
        return Instance(id=instance_name, src='jr://fixture/{}'.format(instance_name))


@register_factory('commcare')
def commcare_fixture_instances(domain, instance_name):
    if instance_name == 'commcare:reports' and toggles.MOBILE_UCR.enabled(domain):
        return Instance(id=instance_name, src='jr://fixture/{}'.format(instance_name))


def _commcare_reports_instances(domain, instance_name, prefix):
    from corehq.apps.app_manager.suite_xml.features.mobile_ucr import get_uuids_by_instance_id
    if instance_name.startswith(prefix) and toggles.MOBILE_UCR.enabled(domain):
        instance_id = instance_name[len(prefix):]
        uuid = get_uuids_by_instance_id(domain).get(instance_id, [instance_id])[0]
        return Instance(id=instance_name, src='jr://fixture/{}{}'.format(prefix, uuid))


@register_factory('commcare-reports')
def commcare_reports_fixture_instances(domain, instance_name):
    return _commcare_reports_instances(domain, instance_name, 'commcare-reports:')


@register_factory('commcare-reports-filters')
def commcare_reports_filters_instances(domain, instance_name):
    return _commcare_reports_instances(domain, instance_name, 'commcare-reports-filters:')


@register_factory('locations')
def location_fixture_instances(domain, instance_name):
    from corehq.apps.locations.models import LocationFixtureConfiguration
    if (toggles.HIERARCHICAL_LOCATION_FIXTURE.enabled(domain)
            and not LocationFixtureConfiguration.for_domain(domain).sync_flat_fixture):
        return Instance(id=instance_name, src='jr://fixture/commtrack:{}'.format(instance_name))
    return Instance(id=instance_name, src='jr://fixture/{}'.format(instance_name))


@register_factory('related_locations')
def related_locations_fixture_instances(domain, instance_name):
    if instance_name == 'related_locations' and toggles.RELATED_LOCATIONS.enabled(domain):
        return Instance(id=instance_name, src='jr://fixture/{}'.format(instance_name))


def get_all_instances_referenced_in_xpaths(domain, xpaths):
    instance_re = r"""instance\(['"]([\w\-:]+)['"]\)"""
    instances = set()
    unknown_instance_ids = set()
    for xpath in xpaths:
        instance_names = re.findall(instance_re, xpath, re.UNICODE)
        for instance_name in instance_names:
            try:
                scheme, _ = instance_name.split(':', 1)
            except ValueError:
                scheme = instance_name if instance_name == 'locations' else None

            factory = get_instance_factory(scheme)
            instance = factory(domain, instance_name)
            if instance:
                instances.add(instance)
            else:
                class UnicodeWithContext(six.text_type):
                    pass
                instance_name = UnicodeWithContext(instance_name)
                instance_name.xpath = xpath
                unknown_instance_ids.add(instance_name)
    return instances, unknown_instance_ids
