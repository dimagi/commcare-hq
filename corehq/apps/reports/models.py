from datetime import datetime

from django.conf import settings
from django.db import models
from django.utils.html import format_html
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy, gettext_noop


from dimagi.ext.couchdbkit import IntegerProperty

from corehq.apps.users.models import CommCareUser


class HQUserType(object):
    ACTIVE = 0
    DEMO_USER = 1
    ADMIN = 2
    UNKNOWN = 3
    COMMTRACK = 4
    DEACTIVATED = 5
    WEB = 6
    human_readable = [settings.COMMCARE_USER_TERM,
                      gettext_noop("demo_user"),
                      gettext_noop("admin"),
                      gettext_noop("Unknown Users"),
                      gettext_noop("CommCare Supply"),
                      gettext_noop("Deactivated Mobile Workers"),
                      gettext_noop("Web Users"), ]
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
        return [HQUserToggle(i, str(i) in ufilter) for i in range(cls.count)]


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
            klass=self.__class__.__name__,
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
            final = format_html('{} <strong>[unregistered]</strong>', self.username)
        elif self.filter_flag == HQUserType.DEMO_USER:
            final = format_html('<strong>{}</strong>', self.username)
        else:
            final = format_html('<strong>{}</strong> ({})', self.username, self.user_id)
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


class TableauServer(models.Model):
    SERVER_TYPES = (
        ('server', gettext_lazy('Tableau Server')),
        ('online', gettext_lazy('Tableau Online')),
    )
    domain = models.CharField(max_length=64, default='')
    server_type = models.CharField(max_length=6, choices=SERVER_TYPES, default='server')
    server_name = models.CharField(max_length=128)
    validate_hostname = models.CharField(max_length=128, default='', blank=True)
    target_site = models.CharField(max_length=64, default='Default')

    def __str__(self):
        return '{server} {server_type} {site}'.format(server=self.server_name,
                                                      server_type=self.server_type,
                                                      site=self.target_site)


class TableauVisualization(models.Model):
    title = models.CharField(max_length=32, null=True)
    domain = models.CharField(max_length=64)
    server = models.ForeignKey(TableauServer, on_delete=models.CASCADE)
    view_url = models.CharField(max_length=256)
    upstream_id = models.CharField(max_length=32, null=True)

    @property
    def name(self):
        return '/'.join(self.view_url.split('?')[0].split('/')[-2:])

    def __str__(self):
        return '{domain} {server} {view}'.format(domain=self.domain,
                                                 server=self.server,
                                                 view=self.view_url[0:64])

    @classmethod
    def for_user(cls, domain, couch_user):
        items = [
            viz
            for viz in TableauVisualization.objects.filter(domain=domain)
            if couch_user.can_view_tableau_viz(domain, f"{viz.id}")
        ]
        return sorted(items, key=lambda v: v.name.lower())


class TableauConnectedApp(models.Model):
    app_client_id = models.CharField(max_length=32)
    secret_id = models.CharField(max_length=64)
    encrypted_secret_value = models.CharField(max_length=64)
    server = models.OneToOneField(TableauServer, on_delete=models.CASCADE)

    def __str__(self):
        return 'App client ID: {app_client_id},  Server: {server}'.format(app_client_id=self.app_client_id,
                                                                          server=self.server)
