from collections import defaultdict
from functools import partial
from operator import itemgetter
from xml.etree import cElementTree as ElementTree

from casexml.apps.phone.fixtures import FixtureProvider
from casexml.apps.phone.utils import (
    GLOBAL_USER_ID,
    get_or_cache_global_fixture,
)
from corehq.apps.fixtures.dbaccessors import iter_fixture_items_for_data_type
from corehq.apps.fixtures.exceptions import FixtureTypeCheckError
from corehq.apps.fixtures.models import FIXTURE_BUCKET, FixtureDataItem, FixtureDataType
from corehq.apps.products.fixtures import product_fixture_generator_json
from corehq.apps.programs.fixtures import program_fixture_generator_json
from corehq.util.metrics import metrics_histogram
from corehq.util.xml_utils import serialize
from .utils import clean_fixture_field_name, get_index_schema_node


def item_lists_by_domain(domain):
    ret = list()
    for data_type in FixtureDataType.by_domain(domain):
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
            'id': data_type.tag,
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


def item_lists_by_app(app):
    LOOKUP_TABLE_FIXTURE = 'lookup_table_fixture'
    REPORT_FIXTURE = 'report_fixture'
    lookup_lists = item_lists_by_domain(app.domain).copy()
    for item in lookup_lists:
        item['fixture_type'] = LOOKUP_TABLE_FIXTURE

    report_configs = [
        report_config
        for module in app.get_report_modules()
        for report_config in module.report_configs
    ]
    ret = list()
    for config in report_configs:
        uri = 'jr://fixture/commcare-reports:%s' % (config.uuid)
        ret.append({
            'id': config.uuid,
            'uri': uri,
            'path': "/rows/row",
            'name': config.header.get(app.default_language),
            'structure': {},
            'fixture_type': REPORT_FIXTURE,
        })
    return lookup_lists + ret


class ItemListsProvider(FixtureProvider):
    id = 'item-list'

    def __call__(self, restore_state):
        restore_user = restore_state.restore_user
        global_types = {}
        user_types = {}
        for data_type in FixtureDataType.by_domain(restore_user.domain):
            if data_type.is_global:
                global_types[data_type._id] = data_type
            else:
                user_types[data_type._id] = data_type
        items = []
        user_items_count = 0
        if global_types:
            global_items = self.get_global_items(global_types, restore_state)
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

    def get_global_items(self, global_types, restore_state):
        domain = restore_state.restore_user.domain
        data_fn = partial(self._get_global_items, global_types, domain)
        return get_or_cache_global_fixture(restore_state, FIXTURE_BUCKET, '', data_fn)

    def _get_global_items(self, global_types, domain):
        def get_items_by_type(data_type):
            for item in iter_fixture_items_for_data_type(domain, data_type._id, wrap=False):
                self._set_cached_type(item, data_type)
                yield item

        return self._get_fixtures(global_types, get_items_by_type, GLOBAL_USER_ID)

    def get_user_items_and_count(self, user_types, restore_user):
        user_items_count = 0
        items_by_type = defaultdict(list)
        for item in restore_user.get_fixture_data_items():
            data_type = user_types.get(item['data_type_id'])
            if data_type:
                self._set_cached_type(item, data_type)
                items_by_type[data_type].append(item)
                user_items_count += 1

        def get_items_by_type(data_type):
            return sorted(items_by_type.get(data_type, []),
                          key=itemgetter('sort_key'))

        return self._get_fixtures(user_types, get_items_by_type, restore_user.user_id), user_items_count

    def _set_cached_type(self, item, data_type):
        # set the cached version used by the object so that it doesn't
        # have to do another db trip later
        item['_data_type'] = data_type

    def _get_fixtures(self, data_types, get_items_by_type, user_id):
        fixtures = []
        for data_type in sorted(data_types.values(), key=itemgetter('tag')):
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
            try:
                xml = self.to_xml(item)
            except KeyError:
                # catch docs missed in prior lazy migrations
                xml = self.to_xml(FixtureDataItem.wrap(item).to_json())
            item_list_element.append(xml)
        return fixture_element

    def _get_schema_element(self, data_type):
        attrs_to_index = [field.field_name for field in data_type.fields if field.is_indexed]
        fixture_id = ':'.join((self.id, data_type.tag))
        return get_index_schema_node(fixture_id, attrs_to_index)

    @staticmethod
    def to_xml(item):
        xData = ElementTree.Element(item['_data_type'].tag)
        for attribute in item['_data_type'].item_attributes:
            try:
                xData.attrib[attribute] = serialize(item['item_attributes'][attribute])
            except KeyError as e:
                # This should never occur, buf if it does, the OTA restore on mobile will fail and
                # this error would have been raised and email-logged.
                raise FixtureTypeCheckError(
                    "Table with tag %s has an item with id %s that doesn't have an attribute as defined in its types definition"
                    % (item['_data_type'].tag, item['_id'])
                )
        for field in item['_data_type'].fields:
            escaped_field_name = clean_fixture_field_name(field.field_name)
            if field.field_name not in item.get('fields', {}):
                xField = ElementTree.SubElement(xData, escaped_field_name)
                xField.text = ""
            else:
                for field_with_attr in item['fields'][field.field_name]['field_list']:
                    xField = ElementTree.SubElement(xData, escaped_field_name)
                    xField.text = serialize(field_with_attr['field_value'])
                    for attribute in field_with_attr['properties']:
                        val = field_with_attr['properties'][attribute]
                        xField.attrib[attribute] = serialize(val)

        return xData


item_lists = ItemListsProvider()
