from collections import defaultdict
import re
from corehq import toggles
from corehq.apps.app_manager.suite_xml.contributors import PostProcessor
from corehq.apps.app_manager.suite_xml.xml_models import Instance
from dimagi.utils.decorators.memoized import memoized


class EntryInstances(PostProcessor):

    def update_suite(self):
        for entry in self.suite.entries:
            self.add_entry_instances(entry)

    def add_entry_instances(self, entry):
        xpaths = self._get_all_xpaths_for_entry(entry)
        instances, unknown_instance_ids = get_all_instances_referenced_in_xpaths(self.app.domain, xpaths)
        entry.require_instances(instances=instances, instance_ids=unknown_instance_ids)

    def _get_all_xpaths_for_entry(self, entry):
        relevance_by_menu, menu_by_command = self._get_menu_relevance_mapping()
        details_by_id = self._get_detail_mapping()
        detail_ids = set()
        xpaths = set()

        for datum in entry.datums:
            detail_ids.add(datum.detail_confirm)
            detail_ids.add(datum.detail_select)
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


INSTANCE_BY_ID = {
    'groups': Instance(id='groups', src='jr://fixture/user-groups'),
    'reports': Instance(id='reports', src='jr://fixture/commcare:reports'),
    'ledgerdb': Instance(id='ledgerdb', src='jr://instance/ledgerdb'),
    'casedb': Instance(id='casedb', src='jr://instance/casedb'),
    'commcaresession': Instance(id='commcaresession', src='jr://instance/session'),
}


@register_factory(*INSTANCE_BY_ID.keys())
def preset_instances(instance_name):
    return INSTANCE_BY_ID.get(instance_name, None)


@register_factory('item-list', 'schedule', 'indicators', 'commtrack')
@memoized
def generic_fixture_instances(instance_name):
    return Instance(id=instance_name, src='jr://fixture/{}'.format(instance_name))


def get_all_instances_referenced_in_xpaths(domain, xpaths):
    known_instances, unknown_instance_ids = _get_known_instances(xpaths)
    feature_flag_instances = _get_feature_flag_instances(domain, required_instances=unknown_instance_ids)
    known_instances |= feature_flag_instances
    return known_instances, unknown_instance_ids


def _get_known_instances(xpaths):
    instance_re = r"""instance\(['"]([\w\-:]+)['"]\)"""
    instances = set()
    unknown_instance_ids = set()
    for xpath in xpaths:
        instance_names = re.findall(instance_re, xpath)
        for instance_name in instance_names:
            try:
                scheme, _ = instance_name.split(':', 1)
            except ValueError:
                scheme = None

            factory = get_instance_factory(scheme)
            instance = factory(instance_name)
            if instance:
                instances.add(instance)
            else:
                class UnicodeWithContext(unicode):
                    pass
                instance_name = UnicodeWithContext(instance_name)
                instance_name.xpath = xpath
                unknown_instance_ids.add(instance_name)
    return instances, unknown_instance_ids


def _get_feature_flag_instances(domain, required_instances):
    feature_flag_instances = set()

    def _add_instance(instance_id):
        if instance_id in required_instances:
            feature_flag_instances.add(
                Instance(id=instance_id, src='jr://fixture/{}'.format(instance_id))
            )
            required_instances.remove(instance_id)

    if toggles.CUSTOM_CALENDAR_FIXTURE.enabled(domain):
        _add_instance('enikshay:calendar')
    if toggles.MOBILE_UCR.enabled(domain) and 'commcare:reports' in required_instances:
        _add_instance('commcare:reports')

    LOCATIONS = 'locations'
    if LOCATIONS in required_instances:
        if toggles.FLAT_LOCATION_FIXTURE.enabled(domain):
            feature_flag_instances.add(
                Instance(id=LOCATIONS, src='jr://fixture/{}'.format(LOCATIONS))
            )
        else:
            feature_flag_instances.add(
                Instance(id=LOCATIONS, src='jr://fixture/commtrack:{}'.format(LOCATIONS))
            )
        required_instances.remove(LOCATIONS)


    return feature_flag_instances
