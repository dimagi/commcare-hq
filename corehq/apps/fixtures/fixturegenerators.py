from collections import defaultdict
from operator import attrgetter
from xml.etree import cElementTree as ElementTree

from casexml.apps.phone.fixtures import FixtureProvider
from casexml.apps.phone.utils import (
    GLOBAL_USER_ID,
    record_datadog_metric,
    get_cached_fixture_items,
    cache_fixture_items_data,
    write_fixture_items_to_io,
)
from corehq.apps.fixtures.exceptions import FixtureTypeCheckError
from corehq.apps.fixtures.models import fixture_bucket, LookupTable, LookupTableRow
from corehq.apps.products.fixtures import product_fixture_generator_json
from corehq.apps.programs.fixtures import program_fixture_generator_json
from corehq.util.metrics import metrics_histogram
from corehq.util.xml_utils import serialize
from .utils import clean_fixture_field_name, get_index_schema_node
from dimagi.utils.couch import CriticalSection

LOOKUP_TABLE_FIXTURE = 'lookup_table_fixture'
REPORT_FIXTURE = 'report_fixture'


def item_lists_by_domain(domain, namespace_ids=False):
    ret = list()
    for data_type in LookupTable.objects.by_domain(domain):
        structure = {
            f.field_name: {
                'name': f.field_name,
                'no_option': True
            } for f in data_type.fields
        }

        for attr in data_type.item_attributes:
            structure['@' + attr] = {'name': attr, 'no_option': True}

        uri = 'jr://fixture/%s:%s' % (ItemListsProvider.id, data_type.tag)
        ret.append({
            'id': f"{ItemListsProvider.id}:{data_type.tag}" if namespace_ids else data_type.tag,
            'uri': uri,
            'path': "/{tag}_list/{tag}".format(tag=data_type.tag),
            'name': data_type.tag,
            'structure': structure,
        })
    ret = sorted(ret, key=lambda x: x['name'].lower())

    products = product_fixture_generator_json(domain)
    if products:
        ret.append(products)
    programs = program_fixture_generator_json(domain)
    if programs:
        ret.append(programs)
    return ret


def item_lists_by_app(app, module):
    lookup_lists = item_lists_by_domain(app.domain, namespace_ids=True).copy()
    for item in lookup_lists:
        item['fixture_type'] = LOOKUP_TABLE_FIXTURE

    report_configs = [
        report_config
        for module in app.get_report_modules()
        for report_config in module.report_configs
    ]
    if not report_configs:
        return lookup_lists

    legacy_instance_ids = {
        prop.itemset.instance_id
        for prop in module.search_config.properties
        if prop.itemset.instance_id and 'commcare-reports:' not in prop.itemset.instance_id
    }
    ret = list()
    for config in report_configs:
        instance_id = f'commcare-reports:{config.uuid}'  # follow HQ instance ID convention
        uri = f'jr://fixture/{instance_id}'
        item = {
            'id': instance_id,
            'uri': uri,
            'path': "/rows/row",
            'name': config.header.get(app.default_language),
            'structure': {},
            'fixture_type': REPORT_FIXTURE,
        }
        ret.append(item)
        if config.uuid in legacy_instance_ids:
            # add in item with the legacy ID to support apps using the old ID format
            legacy_item = item.copy()
            legacy_item['id'] = config.uuid
            legacy_item['name'] = f"{item['name']} (legacy)"
            ret.append(legacy_item)
    return lookup_lists + ret


def get_global_items_by_domain(domain, case_id):
    global_types = LookupTable.objects.by_domain(domain).filter(is_global=True)
    return ItemListsProvider().get_global_items(domain, global_types, case_id, False)


class ItemListsProvider(FixtureProvider):
    id = 'item-list'

    def __call__(self, restore_state):
        restore_user = restore_state.restore_user
        global_types = []
        user_types = {}
        should_full_sync = not restore_state.last_sync_log or not restore_state.last_sync_log.date
        if should_full_sync:
            data_types = LookupTable.objects.by_domain(restore_user.domain)
        else:
            data_types = LookupTable.objects.get_tables_modified_since(restore_user.domain,
                                                                       restore_state.last_sync_log.date)
        for data_type in data_types:
            if data_type.is_global:
                global_types.append(data_type)
            else:
                user_types[data_type.id] = data_type
        items = []
        user_items_count = 0
        if global_types:
            global_items = self.get_global_items(restore_state.restore_user.domain, global_types,
                                                 restore_state.restore_user.user_id,
                                                 restore_state.overwrite_cache)
            items.extend(global_items)
        if user_types:
            user_items, user_items_count = self.get_user_items_and_count(user_types, restore_user)
            items.extend(user_items)

        metrics_histogram(
            'commcare.fixtures.item_lists.user',
            user_items_count,
            bucket_tag='items',
            buckets=[1, 100, 1000, 10000, 30000, 100000, 300000, 1000000],
            bucket_unit='',
            tags={
                'domain': restore_user.domain
            }
        )
        return items

    def get_global_items(self, domain, global_types, user_id, overwrite_cache):
        """
        :param user_id: User's id, if this is for case restore, then pass in case id
        """
        return [fixture for fixture in [
            self._get_or_cache_global_fixture(
                domain,
                global_type,
                user_id,
                overwrite_cache,
            ) for global_type in sorted(global_types, key=lambda global_type: global_type.tag)
        ] if fixture != b'']

    def _get_or_cache_global_fixture(self, domain, global_type, user_id, overwrite_cache=False):
        """
        Get the fixture data for a global fixture (one that does not vary by user).

        :param domain: The domain to get or cache the fixture
        :param user_id: User's id, if this is for case restore, then pass in case id
        :param overwrite_cache: a boolean property from RestoreState object, default is False
        :return: a byte string representation of the fixture
        """
        data = None
        key = fixture_bucket(global_type.id, domain)

        if not overwrite_cache:
            data = get_cached_fixture_items(key)
            record_datadog_metric('cache_miss' if data is None else 'cache_hit', domain)

        if data is None:
            with CriticalSection([key]):
                if not overwrite_cache:
                    # re-check cache to avoid re-computing it
                    data = get_cached_fixture_items(key)
                if data is None:
                    record_datadog_metric('generate', domain)
                    items = self._get_global_items(global_type, domain)
                    with write_fixture_items_to_io(items) as io_data:
                        data = io_data.getvalue()
                        cache_fixture_items_data(io_data, domain, '', key)

        global_id = GLOBAL_USER_ID.encode('utf-8')
        b_user_id = user_id.encode('utf-8')
        return data.replace(global_id, b_user_id)

    def _get_global_items(self, global_type, domain):
        def get_items_by_type(data_type):
            return LookupTableRow.objects.iter_rows(domain, table_id=data_type.id)
        return self._get_fixtures({global_type.id: global_type}, get_items_by_type, GLOBAL_USER_ID)

    def get_user_items_and_count(self, user_types, restore_user):
        user_items_count = 0
        items_by_type = defaultdict(list)
        for item in restore_user.get_fixture_data_items():
            data_type = user_types.get(item.table_id)
            if data_type:
                items_by_type[data_type].append(item)
                user_items_count += 1

        def get_items_by_type(data_type):
            return items_by_type.get(data_type, [])

        return self._get_fixtures(user_types, get_items_by_type, restore_user.user_id), user_items_count

    def _get_fixtures(self, data_types, get_items_by_type, user_id):
        fixtures = []
        for data_type in sorted(data_types.values(), key=attrgetter('tag')):
            if data_type.is_indexed:
                fixtures.append(self._get_schema_element(data_type))
            items = get_items_by_type(data_type)
            fixtures.append(self._get_fixture_element(data_type, user_id, items))
        return fixtures

    def _get_fixture_element(self, data_type, user_id, items):
        attrib = {
            'id': ':'.join((self.id, data_type.tag)),
            'user_id': user_id
        }
        if data_type.is_indexed:
            attrib['indexed'] = 'true'
        fixture_element = ElementTree.Element('fixture', attrib)
        item_list_element = ElementTree.Element('%s_list' % data_type.tag)
        fixture_element.append(item_list_element)
        for item in items:
            xml = self.to_xml(item, data_type)
            item_list_element.append(xml)
        return fixture_element

    def _get_schema_element(self, data_type):
        attrs_to_index = [field.field_name for field in data_type.fields if field.is_indexed]
        fixture_id = ':'.join((self.id, data_type.tag))
        return get_index_schema_node(fixture_id, attrs_to_index)

    @staticmethod
    def to_xml(item, data_type):
        xData = ElementTree.Element(data_type.tag)
        for attribute in data_type.item_attributes:
            try:
                xData.attrib[attribute] = serialize(item.item_attributes[attribute])
            except KeyError:
                # This should never occur, buf if it does, the OTA restore on mobile will fail and
                # this error would have been raised and email-logged.
                raise FixtureTypeCheckError(
                    f"Table with tag {data_type.tag} has an item with "
                    f"id {item.id.hex} that doesn't have an attribute as "
                    "defined in its types definition"
                )
        for field in data_type.fields:
            escaped_field_name = clean_fixture_field_name(field.field_name)
            if field.field_name not in item.fields:
                xField = ElementTree.SubElement(xData, escaped_field_name)
                xField.text = ""
            else:
                for field_with_attr in item.fields[field.field_name]:
                    xField = ElementTree.SubElement(xData, escaped_field_name)
                    xField.text = serialize(field_with_attr.value)
                    for attribute, val in field_with_attr.properties.items():
                        xField.attrib[attribute] = serialize(val)

        return xData


item_lists = ItemListsProvider()
