from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime
import logging

from django.core.exceptions import ValidationError
from django.db import models
from django.http import Http404
from django.utils import html
from django.utils.safestring import mark_safe
from django.conf import settings
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_noop
from jsonfield import JSONField

from corehq.apps.app_manager.app_schemas.case_properties import get_case_properties

from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.models import Form, RemoteApp
from corehq.apps.cachehq.mixins import (
    QuickCachedDocumentMixin,
)
from corehq.apps.domain.models import Domain
from corehq.apps.reports.dbaccessors import (
    hq_group_export_configs_by_domain,
)
from corehq.apps.reports.display import xmlns_to_name
from corehq.apps.reports.exportfilters import (
    default_case_filter,
    default_form_filter,
    form_matches_users,
    is_commconnect_form,
)
from corehq.apps.users.models import CommCareUser, CouchUser
from corehq.util.python_compatibility import soft_assert_type_text
from corehq.util.quickcache import quickcache

from couchexport.models import SavedExportSchema, GroupExportConfiguration, SplitColumn
from couchexport.transforms import couch_to_excel_datetime, identity
from couchexport.util import SerializableFunction
from couchforms.filters import instances
from dimagi.ext.couchdbkit import *
from memoized import memoized
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


class HQExportSchema(SavedExportSchema):
    doc_type = 'SavedExportSchema'
    domain = StringProperty()
    transform_dates = BooleanProperty(default=True)

    @property
    def global_transform_function(self):
        if self.transform_dates:
            return couch_to_excel_datetime
        else:
            return identity

    @classmethod
    def wrap(cls, data):
        if 'transform_dates' not in data:
            data['transform_dates'] = False
        self = super(HQExportSchema, cls).wrap(data)
        if not self.domain:
            self.domain = self.index[0]
        return self


class FormExportSchema(HQExportSchema):
    doc_type = 'SavedExportSchema'
    app_id = StringProperty()
    include_errors = BooleanProperty(default=False)
    split_multiselects = BooleanProperty(default=False)
    _default_type = 'form'

    def update_schema(self):
        super(FormExportSchema, self).update_schema()
        if self.split_multiselects:
            self.update_question_schema()
            for column in [column for table in self.tables for column in table.columns]:
                if isinstance(column, SplitColumn):
                    question = self.question_schema.question_schema.get(column.index)
                    # this is to workaround a bug where a "special" column was incorrectly
                    # being flagged as a SplitColumn.
                    # https://github.com/dimagi/commcare-hq/pull/9915
                    if question:
                        column.options = question.options
                        column.ignore_extras = True

    def update_question_schema(self):
        schema = self.question_schema
        schema.update_schema()

    @property
    def question_schema(self):
        from corehq.apps.export.models import FormQuestionSchema
        return FormQuestionSchema.get_or_create(self.domain, self.app_id, self.xmlns)

    @property
    @memoized
    def app(self):
        if self.app_id:
            try:
                return get_app(self.domain, self.app_id, latest=True)
            except Http404:
                logging.error('App %s in domain %s not found for export %s' % (
                    self.app_id,
                    self.domain,
                    self.get_id
                ))
                raise AppNotFound()
        else:
            return None

    @classmethod
    def wrap(cls, data):
        self = super(FormExportSchema, cls).wrap(data)
        if self.filter_function == 'couchforms.filters.instances':
            # grandfather in old custom exports
            self.include_errors = False
            self.filter_function = None
        return self

    @property
    def filter(self):
        user_ids = set(CouchUser.ids_by_domain(self.domain))
        user_ids.update(CouchUser.ids_by_domain(self.domain, is_active=False))
        user_ids.add('demo_user')

        def _top_level_filter(form):
            # careful, closures used
            return form_matches_users(form, user_ids) or is_commconnect_form(form)

        f = SerializableFunction(_top_level_filter)
        if self.app_id is not None:
            from corehq.apps.reports import util as reports_util
            f.add(reports_util.app_export_filter, app_id=self.app_id)
        if not self.include_errors:
            f.add(instances)
        actual = SerializableFunction(default_form_filter, filter=f)
        return actual

    @property
    def domain(self):
        return self.index[0]

    @property
    def xmlns(self):
        return self.index[1]

    @property
    def formname(self):
        return xmlns_to_name(self.domain, self.xmlns, app_id=self.app_id)

    @property
    @memoized
    def question_order(self):
        try:
            if not self.app:
                return []
        except AppNotFound:
            if settings.DEBUG:
                return []
            raise
        else:
            questions = self.app.get_questions(self.xmlns)

        order = []
        for question in questions:
            if not question['value']:  # question probably belongs to a broken form
                continue
            index_parts = question['value'].split('/')
            assert index_parts[0] == ''
            index_parts[1] = 'form'
            index = '.'.join(index_parts[1:])
            order.append(index)

        return order

    def get_default_order(self):
        return {'#': self.question_order}

    def uses_cases(self):
        if not self.app or isinstance(self.app, RemoteApp):
            return False
        forms = self.app.get_forms_by_xmlns(self.xmlns)
        for form in forms:
            if isinstance(form, Form):
                if bool(form.active_actions()):
                    return True
        return False


class CaseExportSchema(HQExportSchema):
    doc_type = 'SavedExportSchema'
    _default_type = 'case'

    @property
    def filter(self):
        return SerializableFunction(default_case_filter)

    @property
    def domain(self):
        return self.index[0]

    @property
    def domain_obj(self):
        return Domain.get_by_name(self.domain)

    @property
    def case_type(self):
        return self.index[1]

    @property
    def applications(self):
        return self.domain_obj.full_applications(include_builds=False)

    @property
    def case_properties(self):
        props = set([])

        for app in self.applications:
            prop_map = get_case_properties(app, [self.case_type], defaults=("name",))
            props |= set(prop_map[self.case_type])

        return props

    @property
    def has_case_history_table(self):
        return False  # This check is only for new exports


def _apply_mapping(export_tables, mapping_dict):
    def _clean(tabledata):
        def _clean_tablename(tablename):
            return mapping_dict.get(tablename, tablename)
        return (_clean_tablename(tabledata[0]), tabledata[1])
    return list(map(_clean, export_tables))


def _apply_removal(export_tables, removal_list):
    return [tabledata for tabledata in export_tables if not tabledata[0] in removal_list]


class HQGroupExportConfiguration(QuickCachedDocumentMixin, GroupExportConfiguration):
    """
    HQ's version of a group export, tagged with a domain
    """
    domain = StringProperty()

    def get_custom_exports(self):

        def _rewrap(export):
            # custom wrap if relevant
            try:
                return {
                    'form': FormExportSchema,
                    'case': CaseExportSchema,
                }[export.type].wrap(export._doc)
            except KeyError:
                return export

        for custom in list(self.custom_export_ids):
            custom_export = self._get_custom(custom)
            if custom_export:
                yield _rewrap(custom_export)

    @classmethod
    @quickcache(['cls.__name__', 'domain'])
    def by_domain(cls, domain):
        return hq_group_export_configs_by_domain(domain)

    @classmethod
    def get_for_domain(cls, domain):
        """
        For when we only expect there to be one of these per domain,
        which right now is always.
        """
        groups = cls.by_domain(domain)
        if groups:
            if len(groups) > 1:
                logging.error("Domain %s has more than one group export config! This is weird." % domain)
            return groups[0]
        return HQGroupExportConfiguration(domain=domain)

    def clear_caches(self):
        super(HQGroupExportConfiguration, self).clear_caches()
        self.by_domain.clear(self.__class__, self.domain)


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
