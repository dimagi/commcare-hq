from collections import defaultdict
from corehq.form_processor.utils import is_commcarecase
from corehq.apps.groups.models import Group
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.cases import get_owner_id, get_wrapped_owner
from corehq.apps.users.models import CouchUser, CommCareUser, WebUser
import string

UNKNOWN_VALUE = '(?)'


def _get_case_template_info(case):
    return case.to_json()


def _get_web_user_template_info(user):
    return {
        'name': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'phone_number': user.default_phone_number or '',
    }


def _get_mobile_user_template_info(user):
    return {
        'name': user.raw_username,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'phone_number': user.default_phone_number or '',
    }


def _get_system_user_template_info():
    return {
        'name': 'System',
        'first_name': 'System',
        'last_name': '',
        'phone_number': '',
    }


def _get_group_template_info(group):
    return {
        'name': group.name,
    }


def _get_location_template_info(location):
    return {
        'name': location.name,
        'site_code': location.site_code,
    }


def _get_obj_template_info(obj):
    if is_commcarecase(obj):
        return _get_case_template_info(obj)
    elif isinstance(obj, WebUser):
        return _get_web_user_template_info(obj)
    elif isinstance(obj, CommCareUser):
        return _get_mobile_user_template_info(obj)
    elif isinstance(obj, Group):
        return _get_group_template_info(obj)
    elif isinstance(obj, SQLLocation):
        return _get_location_template_info(obj)

    return {}


class MessagingTemplateRenderer(object):
    context_params = None

    def __init__(self):
        self.context_params = defaultdict(lambda: SimpleMessagingTemplateParam(UNKNOWN_VALUE))

    def set_context_param(self, name, value):
        self.context_params[name] = value

    def render(self, message):
        return string.Formatter().vformat(str(message), [], self.context_params)


class SimpleMessagingTemplateParam(object):

    def __init__(self, value):
        # Define all internal attributes as private so that they can't be
        # accessed directly from a rendering context
        self.__value = value

    def __format__(self, format_spec):
        """
        __format__ is what is called when this object is to be rendered
        in a string.
        """
        return str(self.__value)

    def __getattr__(self, item):
        """
        __getattr__ is what is called when an attribute of this object is
        accessed in a rendering, for example {object.attribute}. It should
        return the attribute, which will itself be rendered by its own
        __format__ method.

        A simple value doesn't have any attributes, so trying to
        access any attributes will always return another
        SimpleMessagingTemplateParam that renders to the unknown value.
        """
        return SimpleMessagingTemplateParam(UNKNOWN_VALUE)


class SimpleDictTemplateParam(object):

    def __init__(self, dict_of_values):
        # Define all internal attributes as private so that they can't be
        # accessed directly from a rendering context
        self.__dict_of_values = dict_of_values

    def __format__(self, format_spec):
        """
        __format__ is what is called when this object is to be rendered
        in a string.

        We don't render the full dictionary, so instead we render as the
        unknown value.
        """
        return UNKNOWN_VALUE

    def __getattr__(self, item):
        """
        __getattr__ is what is called when an attribute of this object is
        accessed in a rendering, for example {object.attribute}. It should
        return the attribute, which will itself be rendered by its own
        __format__ method.

        So we return a SimpleMessagingTemplateParam that either renders to the
        item in the dictionary or to the unknown value if it doesn't exist.
        """
        if item in self.__dict_of_values:
            return SimpleMessagingTemplateParam(self.__dict_of_values[item])

        return SimpleMessagingTemplateParam(UNKNOWN_VALUE)


class NestedDictTemplateParam(SimpleDictTemplateParam):

    def __init__(self, dict_of_values):
        self.__dict_of_values = dict_of_values

    def __getattr__(self, item):
        """Works just like SimpleDictTemplateParam but it can contain nested dicts"""
        if val := self.__dict_of_values.get(item):
            if isinstance(val, dict):
                return NestedDictTemplateParam(val)

            return SimpleMessagingTemplateParam(val)

        return SimpleMessagingTemplateParam(UNKNOWN_VALUE)


class CaseMessagingTemplateParam(SimpleDictTemplateParam):

    def __init__(self, case):
        super(CaseMessagingTemplateParam, self).__init__(_get_case_template_info(case))

        # Define all internal attributes as private so that they can't be
        # accessed directly from a rendering context
        self.__case = case
        self.__domain = case.domain
        self.__owner_result = None
        self.__parent_result = None
        self.__host_result = None
        self.__last_modified_by_result = None

    def __get_owner_result(self):
        """
        memoized doesn't seem to work with overriding __getattr__ at the same time,
        so we cache the result using a private attribute.
        """
        if self.__owner_result:
            return self.__owner_result

        owner = get_wrapped_owner(get_owner_id(self.__case))
        if isinstance(owner, CouchUser):
            if owner.is_member_of(self.__domain):
                self.__owner_result = SimpleDictTemplateParam(_get_obj_template_info(owner))
        elif isinstance(owner, (Group, SQLLocation)):
            if owner.domain == self.__domain:
                self.__owner_result = SimpleDictTemplateParam(_get_obj_template_info(owner))

        self.__owner_result = self.__owner_result or SimpleMessagingTemplateParam(UNKNOWN_VALUE)
        return self.__owner_result

    def __get_parent_result(self):
        """
        memoized doesn't seem to work with overriding __getattr__ at the same time,
        so we cache the result using a private attribute.
        """
        if self.__parent_result:
            return self.__parent_result

        parent_case = self.__case.parent
        if parent_case:
            self.__parent_result = CaseMessagingTemplateParam(parent_case)
        else:
            self.__parent_result = SimpleMessagingTemplateParam(UNKNOWN_VALUE)

        return self.__parent_result

    def __get_host_result(self):
        """
        memoized doesn't seem to work with overriding __getattr__ at the same time,
        so we cache the result using a private attribute.
        """
        if self.__host_result:
            return self.__host_result

        host_case = self.__case.host
        if host_case:
            self.__host_result = CaseMessagingTemplateParam(host_case)
        else:
            self.__host_result = SimpleMessagingTemplateParam(UNKNOWN_VALUE)

        return self.__host_result

    def __get_last_modified_by_result(self):
        """
        memoized doesn't seem to work with overriding __getattr__ at the same time,
        so we cache the result using a private attribute.
        """
        if self.__last_modified_by_result:
            return self.__last_modified_by_result

        if self.__case.modified_by == 'system':
            self.__last_modified_by_result = SimpleDictTemplateParam(_get_system_user_template_info())
            return self.__last_modified_by_result

        try:
            modified_by = CouchUser.get_by_user_id(self.__case.modified_by)
        except KeyError:
            modified_by = None

        if modified_by:
            self.__last_modified_by_result = SimpleDictTemplateParam(_get_obj_template_info(modified_by))
        else:
            self.__last_modified_by_result = SimpleMessagingTemplateParam(UNKNOWN_VALUE)

        return self.__last_modified_by_result

    def __getattr__(self, item):
        """
        __getattr__ is what is called when an attribute of this object is
        accessed in a rendering, for example {object.attribute}. It should
        return the attribute, which will itself be rendered by its own
        __format__ method.
        """
        if item == 'owner':
            return self.__get_owner_result()
        elif item == 'parent':
            return self.__get_parent_result()
        elif item == 'host':
            return self.__get_host_result()
        elif item == 'last_modified_by':
            return self.__get_last_modified_by_result()

        return super(CaseMessagingTemplateParam, self).__getattr__(item)
