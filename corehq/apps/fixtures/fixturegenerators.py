from collections import defaultdict
from xml.etree import ElementTree
from StringIO import StringIO

from corehq.blobs import get_blob_db
from corehq.blobs.exceptions import NotFound

from casexml.apps.phone.fixtures import FixtureProvider
from corehq.apps.fixtures.models import FixtureDataItem, FixtureDataType, FIXTURE_BUCKET
from corehq.apps.products.fixtures import product_fixture_generator_json
from corehq.apps.programs.fixtures import program_fixture_generator_json


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
            'path': u"/{tag}_list/{tag}".format(tag=data_type.tag),
            'name': data_type.tag,
            'structure': structure,
        })

    products = product_fixture_generator_json(domain)
    if products:
        ret.append(products)
    programs = program_fixture_generator_json(domain)
    if programs:
        ret.append(programs)
    return ret


class ItemListsProvider(FixtureProvider):
    id = 'item-list'

    def __call__(self, restore_state):
        restore_user = restore_state.restore_user
        domain = restore_user.domain
        db = get_blob_db()

        all_types = {t._id: t for t in FixtureDataType.by_domain(domain)}
        global_types = {id: t for id, t in all_types.items() if t.is_global}

        if restore_state.overwrite_cache:
            db.delete(domain, FIXTURE_BUCKET)

        # get global types from the db
        try:
            global_items = [db.get(domain, FIXTURE_BUCKET).read()]
        except NotFound:
            global_items = self.get_global_items(restore_user, global_types)
            db.put(StringIO(" ".join(global_items)), domain, FIXTURE_BUCKET)

        user_items = self.get_user_items(restore_user, all_types, global_types)
        return global_items + user_items

    def _set_cached_type(self, item, data_type):
        # set the cached version used by the object so that it doesn't
        # have to do another db trip later
        item._data_type = data_type

    def get_global_items(self, restore_user, global_types):
        types_sorted_by_tag = sorted(global_types.iteritems(), key=lambda (id_, type_): type_.tag)
        items_by_type = defaultdict(list)
        items = FixtureDataItem.by_data_types(restore_user.domain, global_types)
        for item in items:
            self._set_cached_type(item, global_types[item.data_type_id])
            items_by_type[item.data_type_id].append(item)
        return self._generate_fixture_from_type(restore_user, items_by_type, types_sorted_by_tag)

    def get_user_items(self, restore_user, all_types, global_types):
        if set(all_types) - set(global_types):
            # only query ownership models if there are non-global types
            types_sorted_by_tag = sorted(all_types.iteritems(), key=lambda (id_, type_): type_.tag)

            items_by_type = defaultdict(list)
            for item in restore_user.get_fixture_data_items():
                if item.data_type_id in global_types:
                    continue  # was part of the global type so no need to add here
                try:
                    self._set_cached_type(item, all_types[item.data_type_id])
                except (AttributeError, KeyError):
                    continue
                items_by_type[item.data_type_id].append(item)
            return self._generate_fixture_from_type(restore_user, items_by_type, types_sorted_by_tag)
        return []

    def _generate_fixture_from_type(self, restore_user, items_by_type, types_sorted_by_tag):
        fixtures = []
        for data_type_id, data_type in types_sorted_by_tag:
            if data_type.is_indexed:
                fixtures.append(self._get_schema_element(data_type))
            items = sorted(items_by_type.get(data_type_id, []), key=lambda x: x.sort_key)
            fixtures.append(self._get_fixture_element(data_type, restore_user.user_id, items))
        return fixtures

    def _get_fixture_element(self, data_type, user_id, items):
        attrib = {
            'id': ':'.join((self.id, data_type.tag)),
            'user_id': user_id
        }
        if data_type.is_indexed:
            attrib['indexed'] = 'true'
        fixture_element = ElementTree.Element('fixture', attrib=attrib)
        item_list_element = ElementTree.Element('%s_list' % data_type.tag)
        fixture_element.append(item_list_element)
        for item in items:
            item_list_element.append(item.to_xml())
        if len(fixture_element) == 0:
            # There is a bug on mobile versions prior to 2.27 where
            # a parsing error will cause mobile to ignore the element
            # after this one if this element is empty.
            # So we have to add a dummy empty_element child to prevent
            # this element from being empty.
            ElementTree.SubElement(fixture_element, 'empty_element')
        return ElementTree.tostring(fixture_element, encoding="utf-8")

    def _get_schema_element(self, data_type):
        schema_element = ElementTree.Element(
            'schema',
            attrib={'id': ':'.join((self.id, data_type.tag))}
        )
        indices_element = ElementTree.SubElement(schema_element, 'indices')
        for field in data_type.fields:
            if field.is_indexed:
                index_element = ElementTree.SubElement(indices_element, 'index')
                index_element.text = field.field_name
        return ElementTree.tostring(schema_element, encoding="utf-8")


item_lists = ItemListsProvider()
