from collections import defaultdict
import re
from corehq.apps.app_manager.exceptions import UnknownInstanceError
from corehq.apps.app_manager.suite_xml.basic import SuiteContributor
from corehq.apps.app_manager.suite_xml.utils import get_instance_factory


class EntryInstances(SuiteContributor):
    def contribute(self):
        details_by_id = self.get_detail_mapping()
        relevance_by_menu, menu_by_command = self.get_menu_relevance_mapping()
        for e in self.suite.entries:
            self.add_referenced_instances(e, details_by_id, relevance_by_menu, menu_by_command)

    def get_detail_mapping(self):
        return {detail.id: detail for detail in self.suite.details}

    def get_menu_relevance_mapping(self):
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

    @staticmethod
    def add_referenced_instances(entry, details_by_id, relevance_by_menu, menu_by_command):
        detail_ids = set()
        xpaths = set()

        for datum in entry.datums:
            detail_ids.add(datum.detail_confirm)
            detail_ids.add(datum.detail_select)
            xpaths.add(datum.nodeset)
            xpaths.add(datum.function)
        details = [details_by_id[detail_id] for detail_id in detail_ids
                   if detail_id]

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

        instances = EntryInstances.get_required_instances(xpaths)

        entry.require_instance(*instances)
        
    @staticmethod
    def get_required_instances(xpaths):
        instance_re = r"""instance\(['"]([\w\-:]+)['"]\)"""
        instances = set()
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
                    raise UnknownInstanceError("Instance reference not recognized: {}".format(instance_name))
        return instances
