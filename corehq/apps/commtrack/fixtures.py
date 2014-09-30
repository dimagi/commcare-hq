from xml.etree import ElementTree
from .models import Product, Program


def _simple_fixture_generator(user, name, fields, data_fn, last_sync=None):
    project = user.project
    if not project or not project.commtrack_enabled:
        return []

    # expand this here to prevent two separate couch calls
    data = data_fn()

    if not should_sync(data, last_sync):
        return []

    name_plural = "{}s".format(name)
    root = ElementTree.Element('fixture',
                               attrib={
                                   'id': 'commtrack:{}'.format(name_plural),
                                   'user_id': user.user_id
                               })
    list_elem = ElementTree.Element(name_plural)
    root.append(list_elem)
    for data_item in data:
        item_elem = ElementTree.Element(name, {'id': data_item.get_id})
        list_elem.append(item_elem)
        for field_name in fields:
            field_elem = ElementTree.Element(field_name)

            val = getattr(data_item, field_name, None)
            if isinstance(val, dict):
                if val:
                    for k, v in val.items():
                        sub_el = ElementTree.Element(k)
                        sub_el.text = unicode(v if v is not None else '')
                        field_elem.append(sub_el)

                    item_elem.append(field_elem)
            else:
                field_elem.text = unicode(val if val is not None else '')
                item_elem.append(field_elem)

    return [root]


def should_sync(data, last_sync):
    """
    Determine if a data collection needs to be synced.
    """

    # definitely sync if we haven't synced before
    if not last_sync or not last_sync.date:
        return True

    # check if any items have been modified since last sync
    for data_item in data:
        # >= used because if they are the same second, who knows
        # which actually happened first
        if not data_item.last_modified or data_item.last_modified >= last_sync.date:
            return True

    return False


def product_fixture_generator(user, version, last_sync):
    fields = [
        'name',
        'unit',
        'code',
        'description',
        'category',
        'program_id',
        'cost',
        'product_data'
    ]
    data_fn = lambda: Product.by_domain(user.domain)
    return _simple_fixture_generator(user, "product", fields, data_fn, last_sync)


def program_fixture_generator(user, version, last_sync):
    fields = [
        'name',
        'code'
    ]
    data_fn = lambda: Program.by_domain(user.domain)
    return _simple_fixture_generator(user, "program", fields, data_fn, last_sync)
