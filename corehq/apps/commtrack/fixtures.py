from xml.etree import ElementTree
from .models import Product, Program


def _simple_fixture_generator(user, name, fields, data_fn):
    project = user.project
    if not project or not project.commtrack_enabled:
        return []

    name_plural = "{}s".format(name)
    root = ElementTree.Element('fixture',
                               attrib={
                                   'id': 'commtrack:{}'.format(name_plural),
                                   'user_id': user.user_id
                               })
    list_elem = ElementTree.Element(name_plural)
    root.append(list_elem)
    for data_item in data_fn():
        item_elem = ElementTree.Element(name, {'id': data_item.get_id})
        list_elem.append(item_elem)
        for field_name in fields:
            field_elem = ElementTree.Element(field_name)
            val = getattr(data_item, field_name, None)
            field_elem.text = unicode(val if val is not None else '')
            item_elem.append(field_elem)

    return [root]


def product_fixture_generator(user, version, last_sync):
    fields = [
        'name',
        'unit',
        'code',
        'description',
        'category',
        'program_id',
        'cost'
    ]
    data_fn = lambda: Product.by_domain(user.domain)
    return _simple_fixture_generator(user, "product", fields, data_fn)


def program_fixture_generator(user, version, last_sync):
    fields = [
        'name',
        'code'
    ]
    data_fn = lambda: Program.by_domain(user.domain)
    return _simple_fixture_generator(user, "program", fields, data_fn)
