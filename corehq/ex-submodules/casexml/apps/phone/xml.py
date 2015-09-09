from __future__ import absolute_import
import logging
from xml.sax import saxutils
from xml.etree import ElementTree
from casexml.apps.case import const
from casexml.apps.case.xml import check_version, V1
from casexml.apps.case.xml.generator import get_generator, date_to_xml_string,\
    safe_element

USER_REGISTRATION_XMLNS_DEPRECATED = "http://openrosa.org/user-registration"
USER_REGISTRATION_XMLNS = "http://openrosa.org/user/registration"
VALID_USER_REGISTRATION_XMLNSES = [USER_REGISTRATION_XMLNS_DEPRECATED, USER_REGISTRATION_XMLNS]

SYNC_XMLNS = "http://commcarehq.org/sync"

def escape(o):
    if o is None:
        return ""
    else:
        return saxutils.escape(unicode(o))

def tostring(element):
    # save some typing, force UTF-8
    return ElementTree.tostring(element, encoding="utf-8")


def get_sync_element(restore_id):
    elem = safe_element("Sync")
    elem.attrib = {"xmlns": SYNC_XMLNS}
    elem.append(safe_element("restore_id", restore_id))
    return elem


def get_case_element(case, updates, version=V1):

    check_version(version)

    if case is None:
        logging.error("Can't generate case xml for empty case!")
        return ""

    generator = get_generator(version, case)
    root = generator.get_root_element()

    # if creating, the base data goes there, otherwise it goes in the
    # update block
    do_create = const.CASE_ACTION_CREATE in updates
    do_update = const.CASE_ACTION_UPDATE in updates
    do_index = do_update # NOTE: we may want to differentiate this eventually
    do_attach = do_update
    do_purge = const.CASE_ACTION_PURGE in updates or const.CASE_ACTION_CLOSE in updates
    if do_create:
        # currently the below code relies on the assumption that
        # every create also includes an update
        create_block = generator.get_create_element()
        generator.add_base_properties(create_block)
        root.append(create_block)

    if do_update:
        update_block = generator.get_update_element()
        # if we don't have a create block, also put the base properties
        # in the update block, in case they changed
        if not do_create:
            generator.add_base_properties(update_block)

        # custom properties
        generator.add_custom_properties(update_block)
        if list(update_block):
            root.append(update_block)

    if do_index:
        generator.add_indices(root)
    if do_attach:
        generator.add_attachments(root)

    if do_purge:
        purge_block = generator.get_close_element()
        root.append(purge_block)

    return root


def get_case_xml(case, updates, version=V1):
    check_version(version)
    return tostring(get_case_element(case, updates, version))


def get_registration_element(user):
    root = safe_element("Registration")
    root.attrib = {"xmlns": USER_REGISTRATION_XMLNS}
    root.append(safe_element("username", user.username))
    root.append(safe_element("password", user.password))
    root.append(safe_element("uuid", user.user_id))
    root.append(safe_element("date", date_to_xml_string(user.date_joined)))
    root.append(get_data_element('user_data', user.user_session_data))
    return root


def get_registration_xml(user):
    return tostring(get_registration_element(user))


def get_data_element(name, dict):
    elem = safe_element(name)
    for k, v in dict.items():
        sub_el = safe_element("data", v)
        sub_el.attrib = {"key": k}
        elem.append(sub_el)
    return elem


def synclog_id_from_restore_payload(restore_payload):
    element = ElementTree.fromstring(restore_payload)
    return element.findall('{%s}Sync' % SYNC_XMLNS)[0].findall('{%s}restore_id' % SYNC_XMLNS)[0].text
