from __future__ import absolute_import
from __future__ import unicode_literals
from xml.etree import cElementTree as ElementTree
import six


def simple_fixture_generator(restore_user, id, name, fields, data_fn, last_sync=None, user_id=None):
    """
    Fixture generator used to build commtrack related fixtures such
    as products and programs.
    """
    project = restore_user.project
    if not project or not project.commtrack_enabled:
        return []

    # expand this here to prevent two separate couch calls
    data = data_fn()

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
                        sub_el.text = six.text_type(v if v is not None else '')
                        field_elem.append(sub_el)

                    item_elem.append(field_elem)
            else:
                field_elem.text = six.text_type(val if val is not None else '')
                item_elem.append(field_elem)

    return [root]
