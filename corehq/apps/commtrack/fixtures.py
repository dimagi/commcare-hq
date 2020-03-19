from decimal import Decimal
from xml.etree import cElementTree as ElementTree


def simple_fixture_generator(restore_user, id, name, fields, data, user_id=None):
    """
    Fixture generator used to build commtrack related fixtures such
    as products and programs.
    """
    name_plural = "{}s".format(name)
    root = ElementTree.Element('fixture',
                               {
                                   'id': id,
                                   'user_id': user_id or restore_user.user_id
                               })
    list_elem = ElementTree.Element(name_plural)
    root.append(list_elem)
    for data_item in data:
        # don't add archived items to the restore (these are left
        # in to determine if the fixture needs to be synced)
        if hasattr(data_item, 'is_archived') and data_item.is_archived:
            continue

        item_elem = ElementTree.Element(name, {'id': data_item.get_id})
        list_elem.append(item_elem)
        for field_name in fields:
            field_elem = ElementTree.Element(field_name)

            val = getattr(data_item, field_name, None)
            if isinstance(val, dict):
                if val:
                    for k, v in val.items():
                        sub_el = ElementTree.Element(k)
                        sub_el.text = str(v if v is not None else '')
                        field_elem.append(sub_el)

                    item_elem.append(field_elem)
            else:
                if isinstance(val, Decimal):
                    val = remove_exponent(val)
                field_elem.text = str(val if val is not None else '')
                item_elem.append(field_elem)

    return [root]


def remove_exponent(d: Decimal) -> Decimal:
    """
    Returns ``d`` as its integer representation if it is an integer,
    otherwise strips trailing zeroes and normalizes decimal place.

    >>> Decimal('10.000').normalize()
    Decimal('1E+1')
    >>> remove_exponent(Decimal('10.000'))
    Decimal('10')
    >>> remove_exponent(Decimal('10.010'))
    Decimal('10.01')

    """
    return d.quantize(Decimal(1)) if d == d.to_integral() else d.normalize()
