from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import html
from django.utils.safestring import mark_safe
from django.conf import settings
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_noop
from jsonfield import JSONField

from corehq.apps.users.models import CommCareUser
from corehq.util.python_compatibility import soft_assert_type_text

from dimagi.ext.couchdbkit import *
import six
from six.moves import range
from six.moves import map


class HQUserType(object):
    ACTIVE = 0
    DEMO_USER = 1
    ADMIN = 2
    UNKNOWN = 3
    COMMTRACK = 4
    DEACTIVATED = 5
    WEB = 6
    human_readable = [settings.COMMCARE_USER_TERM,
                      ugettext_noop("demo_user"),
                      ugettext_noop("admin"),
                      ugettext_noop("Unknown Users"),
                      ugettext_noop("CommCare Supply"),
                      ugettext_noop("Deactivated Mobile Workers"),
                      ugettext_noop("Web Users"), ]
    toggle_defaults = (True, False, False, False, False, True, True)
    count = len(human_readable)
    included_defaults = (True, True, True, True, False, True, True)

    @classmethod
    def use_defaults(cls):
        return cls._get_manual_filterset(cls.included_defaults, cls.toggle_defaults)

    @classmethod
    def all_but_users(cls):
        no_users = [True] * cls.count
        no_users[cls.ACTIVE] = False
        return cls._get_manual_filterset(cls.included_defaults, no_users)

    @classmethod
    def commtrack_defaults(cls):
        # this is just a convenience method for clarity on commtrack projects
        return cls.all()

    @classmethod
    def all(cls):
        defaults = (True,) * cls.count
        return cls._get_manual_filterset(defaults, cls.toggle_defaults)

    @classmethod
    def _get_manual_filterset(cls, included, defaults):
        """
        manually construct a filter set. included and defaults should both be
        arrays of booleans mapping to values in human_readable and whether they should be
        included and defaulted, respectively.
        """
        return [HQUserToggle(i, defaults[i]) for i in range(cls.count) if included[i]]

    @classmethod
    def use_filter(cls, ufilter):
        return [HQUserToggle(i, six.text_type(i) in ufilter) for i in range(cls.count)]


class HQToggle(object):
    type = None
    show = False
    name = None

    def __init__(self, type, show, name):
        self.type = type
        self.name = name
        self.show = show

    def __repr__(self):
        return "%(klass)s[%(type)s:%(show)s:%(name)s]" % dict(
            klass = self.__class__.__name__,
            type=self.type,
            name=self.name,
            show=self.show
        )


class HQUserToggle(HQToggle):

    def __init__(self, type, show):
        name = _(HQUserType.human_readable[type])
        super(HQUserToggle, self).__init__(type, show, name)


class TempCommCareUser(CommCareUser):
    filter_flag = IntegerProperty()

    def __init__(self, domain, username, uuid):
        if username == HQUserType.human_readable[HQUserType.DEMO_USER]:
            filter_flag = HQUserType.DEMO_USER
        elif username == HQUserType.human_readable[HQUserType.ADMIN]:
            filter_flag = HQUserType.ADMIN
        else:
            filter_flag = HQUserType.UNKNOWN
        super(TempCommCareUser, self).__init__(
            domain=domain,
            username=username,
            _id=uuid,
            date_joined=datetime.utcnow(),
            is_active=False,
            user_data={},
            first_name='',
            last_name='',
            filter_flag=filter_flag
        )

    def save(self, **params):
        raise NotImplementedError

    @property
    def userID(self):
        return self._id

    @property
    def username_in_report(self):
        if self.filter_flag == HQUserType.UNKNOWN:
            final = mark_safe('%s <strong>[unregistered]</strong>' % html.escape(self.username))
        elif self.filter_flag == HQUserType.DEMO_USER:
            final = mark_safe('<strong>%s</strong>' % html.escape(self.username))
        else:
            final = mark_safe('<strong>%s</strong> (%s)' % tuple(map(html.escape, [self.username, self.user_id])))
        return final

    @property
    def raw_username(self):
        return self.username

    class Meta(object):
        app_label = 'reports'


class AppNotFound(Exception):
    pass


def _apply_mapping(export_tables, mapping_dict):
    def _clean(tabledata):
        def _clean_tablename(tablename):
            return mapping_dict.get(tablename, tablename)
        return (_clean_tablename(tabledata[0]), tabledata[1])
    return list(map(_clean, export_tables))


def _apply_removal(export_tables, removal_list):
    return [tabledata for tabledata in export_tables if not tabledata[0] in removal_list]


def ordering_config_validator(value):

    error = ValidationError(
        _('The config format is invalid'),
        params={'value': value}
    )

    if not isinstance(value, list):
        raise error
    for group in value:
        if not isinstance(group, list) or len(group) != 2:
            raise error
        if not isinstance(group[0], six.string_types):
            raise error
        else:
            soft_assert_type_text(group[0])
        if not isinstance(group[1], list):
            raise error
        for report in group[1]:
            if not isinstance(report, six.string_types):
                raise error
            soft_assert_type_text(report)


class ReportsSidebarOrdering(models.Model):
    domain = models.CharField(
        max_length=256,
        null=False,
        blank=False,
        unique=True
    )
    # Example config value:
    # [
    #     ["Adherence", [
    #         "DynamicReport7613ac1402e2c41db782526e9c43e040",
    #         "DynamicReport1233ac1402e2c41db782526e9c43e040"
    #     ]],
    #     ["Test Results", [
    #         "DynamicReport4563ac1402e2c41db782526e9c43e040",
    #         "DynamicReportmy-static-ucr-id"
    #     ]]
    # ]
    config = JSONField(
        validators=[ordering_config_validator],
        default=list,
        help_text=(
            "An array of arrays. Each array represents a heading in the sidebar navigation. "
            "The first item in each array is a string, which will be the title of the heading. The second item in "
            "the array is another array, each item of which is the name of a report class. Each of these reports "
            "will be listed under the given heading in the sidebar nav."
        )
    )
