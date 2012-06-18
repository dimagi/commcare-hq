from datetime import datetime
import logging
from couchdbkit.exceptions import ResourceConflict
from django.conf import settings
from django.db import models
from couchdbkit.ext.django.schema import Document, StringProperty,\
    BooleanProperty, DateTimeProperty, IntegerProperty, DocumentSchema, SchemaProperty
from dimagi.utils.timezones import fields as tz_fields
from dimagi.utils.couch.database import get_db
from itertools import chain
from langcodes import langs as all_langs
from collections import defaultdict
from copy import deepcopy

lang_lookup = defaultdict(str)

for lang in all_langs:
    lang_lookup[lang['three']] = lang['names'][0] # arbitrarily using the first name if there are multiple
    if lang['two'] != '':
        lang_lookup[lang['two']] = lang['names'][0]

class DomainMigrations(DocumentSchema):
    has_migrated_permissions = BooleanProperty(default=False)

    def apply(self, domain):
        if not self.has_migrated_permissions:
            logging.info("Applying permissions migration to domain %s" % domain.name)
            from corehq.apps.users.models import UserRole, WebUser
            UserRole.init_domain_with_presets(domain.name)
            for web_user in WebUser.by_domain(domain.name):
                try:
                    web_user.save()
                except ResourceConflict:
                    # web_user has already been saved by another thread in the last few seconds
                    pass

            self.has_migrated_permissions = True
            domain.save()

class Domain(Document):
    """Domain is the highest level collection of people/stuff
       in the system.  Pretty much everything happens at the
       domain-level, including user membership, permission to
       see data, reports, charts, etc."""

    name = StringProperty()
    is_active = BooleanProperty()
    is_public = BooleanProperty(default=False)
    date_created = DateTimeProperty()
    default_timezone = StringProperty(default=getattr(settings, "TIME_ZONE", "UTC"))
    case_sharing = BooleanProperty(default=False)
    organization = StringProperty()
    slug = StringProperty() # the slug for this project namespaced within an organization
    
    # domain metadata
    city = StringProperty()
    country = StringProperty()
    region = StringProperty() # e.g. US, LAC, SA, Sub-saharn Africa, East Africa, West Africa, Southeast Asia)
    project_type = StringProperty() # e.g. MCH, HIV
    customer_type = StringProperty() # plus, full, etc.
    is_test = BooleanProperty(default=False)
    description = StringProperty()
    is_shared = BooleanProperty(default=False)

    # App Store/domain copying stuff
    original_doc = StringProperty()
    is_snapshot = BooleanProperty(default=False)
    snapshot_time = DateTimeProperty()
    published = BooleanProperty(default=False)

    migrations = SchemaProperty(DomainMigrations)

    _dirty_fields = ()

    @classmethod
    def wrap(cls, data):
        self = super(Domain, cls).wrap(data)
        if self.get_id:
            self.apply_migrations()
        return self

    @staticmethod
    def active_for_user(user, is_active=True):
        if not hasattr(user,'get_profile'):
            # this had better be an anonymous user
            return []
        from corehq.apps.users.models import CouchUser
        couch_user = CouchUser.from_django_user(user)
        if couch_user:
            domain_names = couch_user.get_domains()
            def log(json):
                doc = json['doc']
                return Domain.wrap(doc)
            return Domain.view("domain/by_status",
                                    keys=[[is_active, d] for d in domain_names],
                                    reduce=False,
                                    wrapper=log,
                                    include_docs=True).all()
        else:
            return []

    @classmethod
    def categories(cls, prefix=''):
        # unichr(0xfff8) is something close to the highest character available
        return [d['key'] for d in cls.view("domain/categories_by_prefix",
                                group=True,
                                startkey=prefix,
                                endkey="%s%c" % (prefix, unichr(0xfff8))).all()]

    def apply_migrations(self):
        self.migrations.apply(self)

    @staticmethod
    def all_for_user(user):
        if not hasattr(user,'get_profile'):
            # this had better be an anonymous user
            return []
        from corehq.apps.users.models import CouchUser
        couch_user = CouchUser.from_django_user(user)
        if couch_user:
            domain_names = couch_user.get_domains()
            return Domain.view("domain/domains",
                                    keys=domain_names,
                                    reduce=False,
                                    include_docs=True).all()
        else:
            return []

    def add(self, model_instance, is_active=True):
        """
        Add something to this domain, through the generic relation.
        Returns the created membership object
        """
        # Add membership info to Couch
        couch_user = model_instance.get_profile().get_couch_user()
        couch_user.add_domain_membership(self.name)
        couch_user.save()

    def applications(self):
        return ApplicationBase.view('app_manager/applications_brief',
                                    startkey=[self.name],
                                    endkey=[self.name, {}]).all()

    def languages(self):
        apps = self.applications()
        return set(chain.from_iterable([a.langs for a in apps]))

    def readable_languages(self):
        return ', '.join(lang_lookup[lang] or lang for lang in self.languages())

    def __unicode__(self):
        return self.name

    @classmethod
    def get_by_name(cls, name):
        result = cls.view("domain/domains",
                            key=name,
                            reduce=False,
                            include_docs=True).first()
        return result

    @classmethod
    def get_by_organization(cls, organization):
        result = cls.view("domain/by_organization",
            startkey=[organization],
            endkey=[organization, {}],
            reduce=False,
            include_docs=True)
        return result

    @classmethod
    def get_by_organization_and_slug(cls, organization, slug):
        result = cls.view("domain/by_organization",
                          key=[organization, slug],
                          reduce=False,
                          include_docs=True)
        return result

    @classmethod
    def get_or_create_with_name(cls, name, is_active=False):
        result = cls.view("domain/domains",
            key=name,
            reduce=False,
            include_docs=True).first()
        if result:
            return result
        else:
            new_domain = Domain(name=name,
                            is_active=is_active,
                            date_created=datetime.utcnow())
            new_domain.save()
            return new_domain

    @classmethod
    def get_all(cls):
        return Domain.view("domain/domains",
                            reduce=False,
                            include_docs=True).all()

    def save_copy(self, new_domain_name=None, user=None):
        if new_domain_name is not None and Domain.get_by_name(new_domain_name):
            return None
        db = get_db()

        str_to_cls = {
            'UserRole': UserRole,
            'Application': Application,
            'RemoteApp': RemoteApp,
            }

        new_id = db.copy_doc(self.get_id)['id']
        if new_domain_name is None:
            new_domain_name = new_id
        new_domain = Domain.get(new_id)
        new_domain.name = new_domain_name
        new_domain.is_snapshot = False
        new_domain.snapshot_time = None
        new_domain.original_doc = self.name
        new_domain.organization = None # TODO: use current user's organization (?)

        for field in self._dirty_fields:
            if hasattr(new_domain, field):
                delattr(new_domain, field)

        for res in db.view('domain/related_to_domain', key=self.name):
            json = res['value']
            doc_type = json['doc_type']
            cls = str_to_cls[doc_type]
            new_id = db.copy_doc(json['_id'])['id']

            print doc_type, new_id, json['_id']

            new_doc = cls.get(new_id)
            for field in self._dirty_fields:
                if hasattr(new_doc, field):
                    delattr(new_doc, field)

            if hasattr(cls, '_meta_fields'):
                for field in cls._meta_fields:
                    if not field.startswith('_') and hasattr(new_doc, field):
                        delattr(new_doc, field)

            new_doc.original_doc = json['_id']
            new_doc.domain = new_domain_name

            new_doc.save()

        new_domain.save()

        if user:
            user.add_domain_membership(new_domain_name)
            user.save()

        return new_domain

    def save_snapshot(self):
        if self.is_snapshot:
            return self
        else:
            copy = self.save_copy()
            if copy is None:
                return None
            copy.is_snapshot = True
            copy.organization = self.organization
            copy.snapshot_time = datetime.now()
            copy.save()
            return copy

    def snapshot_of(self):
        if self.is_snapshot:
            return Domain.get_by_name(self.original_doc)
        else:
            return None

    def copied_from(self):
        original = Domain.get_by_name(self.original_doc)
        if self.is_snapshot:
            return original
        else: # if this is a copy of a snapshot, we want the original, not the snapshot
            return Domain.get_by_name(original.original_doc)

    def from_snapshot(self):
        return not self.is_snapshot and self.original_doc is not None

    def snapshots(self):
        return Domain.view('domain/snapshots', startkey=[self.name], endkey=[self.name, {}])

    def organization_doc(self):
        from corehq.apps.orgs.models import Organization
        return Organization.get_by_name(self.organization)

    def display_name(self):
        if self.is_snapshot:
            return "Snapshot of %s" % self.copied_from.display_name()
        if self.organization:
            return self.slug
        else:
            return self.name

    __str__ = display_name

    def long_display_name(self):
        if self.is_snapshot:
            return "Snapshot of %s &gt; %s" % (self.organization_doc().title, self.copied_from.display_name())
        if self.organization:
            return '%s &gt; %s' % (self.organization_doc().title, self.slug)
        else:
            return self.name

##############################################################################################################
#
# Originally had my own hacky global storage of content type, but it turns out that contenttype.models
# wisely caches content types! No hit to the db beyond the first call - no need for us to do our own 
# custom caching.
#
# See ContentType.get_for_model() code for details.

class OldDomain(models.Model):
    """Domain is the highest level collection of people/stuff
       in the system.  Pretty much everything happens at the 
       domain-level, including user membership, permission to 
       see data, reports, charts, etc."""

    name  = models.CharField(max_length = 64, unique=True)
    is_active = models.BooleanField(default=False)
    timezone = tz_fields.TimeZoneField()
    #description = models.CharField(max_length=255, null=True, blank=True)
    #timezone = models.CharField(max_length=64,null=True)

    class Meta():
        db_table = "domain_domain"
    
    # Utility function - gets active domains in which user has an active membership 
    # Note that User.is_active is not checked here - we're only concerned about usable
    # domains in which the user can theoretically participate, not whether the user 
    # is cleared to login.

    @staticmethod
    def active_for_user(user):
        if not hasattr(user,'get_profile'):
            # this had better be an anonymous user
            return OldDomain.objects.none()
        from corehq.apps.users.models import CouchUser
        couch_user = CouchUser.from_django_user(user)
        if couch_user:
            domain_names = couch_user.get_domains()
            return OldDomain.objects.filter(name__in=domain_names, is_active=True)
        else:
            return OldDomain.objects.none()

    @staticmethod
    def all_for_user(user):
        if not hasattr(user,'get_profile'):
            # this had better be an anonymous user
            return OldDomain.objects.none()
        from corehq.apps.users.models import CouchUser
        couch_user = CouchUser.from_django_user(user)
        if couch_user:
            domain_names = couch_user.get_domains()
            return OldDomain.objects.filter(name__in=domain_names)
        else:
            return OldDomain.objects.none()
    
    def add(self, model_instance, is_active=True):
        """
        Add something to this domain, through the generic relation.
        Returns the created membership object
        """
        # Add membership info to Couch
        couch_user = model_instance.get_profile().get_couch_user()
        couch_user.add_domain_membership(self.name)
        couch_user.save()
        
    def __unicode__(self):
        return self.name

# added after Domain is defined as per http://stackoverflow.com/questions/7199466/how-to-break-import-loop-in-python
# to prevent import loop errors (since corehq.apps.app_manager.models has to import Domain back)
from corehq.apps.app_manager.models import ApplicationBase, import_app, RemoteApp, Application
from corehq.apps.users.models import UserRole
