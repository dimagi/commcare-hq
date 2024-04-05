import logging
from xml.sax import saxutils

import six
from lxml import etree as ElementTree

from casexml.apps.case import const
from casexml.apps.case.xml import V1, check_version
from casexml.apps.case.xml.generator import (
    CaseDBXMLGenerator,
    date_to_xml_string,
    get_generator,
    safe_element,
)
from casexml.apps.phone.exceptions import RestoreException

from corehq.extensions import extension_point

USER_REGISTRATION_XMLNS_DEPRECATED = "http://openrosa.org/user-registration"
USER_REGISTRATION_XMLNS = "http://openrosa.org/user/registration"

SYNC_XMLNS = "http://commcarehq.org/sync"


def escape(o):
    if o is None:
        return ""
    else:
        return saxutils.escape(six.text_type(o))


def tostring(element):
    # save some typing, force UTF-8
    return ElementTree.tostring(element, encoding="utf-8")


def get_sync_element(restore_id=None):
    elem = safe_element("Sync")
    elem.set("xmlns", SYNC_XMLNS)
    if restore_id is not None:
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
    do_index = do_update  # NOTE: we may want to differentiate this eventually
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


def get_casedb_element(case):
    """
    Returns a case element as in the casedb

    <case case_id="" case_type="" owner_id="" status="">
        <case_name/>
        <date_opened/>
        <last_modified/>
        <case_property />
        <index>
            <parent case_type="" relationship="">id</parent>
        </index>
        <attachment>
            <a12345 />
        </attachment>
    </case>
    https://github.com/dimagi/commcare/wiki/casedb
    """
    return CaseDBXMLGenerator(case).get_element()


def get_registration_element(restore_user):
    root = safe_element("Registration")
    root.set("xmlns", USER_REGISTRATION_XMLNS)
    for key, value in get_registration_element_data(restore_user).items():
        if isinstance(value, str) or value is None:
            root.append(safe_element(key, value))
        elif isinstance(value, dict):
            root.append(get_data_element(key, value))
        else:
            raise RestoreException(f"Unexpected data type: {type(value)} ({value})")
    return root


def get_registration_element_data(restore_user):
    return {
        "username": restore_user.username,
        "password": restore_user.password,
        "uuid": restore_user.user_id,
        "date": date_to_xml_string(restore_user.date_joined),
        "user_data": get_user_data_for_restore(restore_user)
    }


def get_user_data_for_restore(restore_user):
    user_data = restore_user.user_session_data
    for custom_user_data in get_custom_user_data_for_restore(restore_user):
        user_data.update(custom_user_data)
    return user_data


@extension_point
def get_custom_user_data_for_restore(restore_user):
    """
    Get additional user data for restore
    :returns: Dict of user data
    """


# Case registration blocks do not have a password
def get_registration_element_for_case(case):
    root = safe_element("Registration")
    root.set("xmlns", USER_REGISTRATION_XMLNS)
    root.append(safe_element("username", case.name))
    root.append(safe_element("password", ""))
    root.append(safe_element("uuid", case.case_id))
    root.append(safe_element("date", date_to_xml_string(case.opened_on)))
    root.append(get_data_element('user_data', {}))
    return root


def get_data_element(name, dict):
    elem = safe_element(name)
    # sorted for deterministic unit tests
    for k, v in sorted(dict.items()):
        sub_el = safe_element("data", v)
        sub_el.set("key", k)
        elem.append(sub_el)
    return elem


def get_progress_element(done=0, total=0, retry_after=0):
    elem = safe_element("progress")
    elem.set('done', str(done))
    elem.set('total', str(total))
    elem.set('retry-after', str(retry_after))
    return elem
