from datetime import datetime, timedelta
import json
import logging
from couchdbkit.exceptions import ResourceConflict
from django.conf import settings
from django.db import models
from couchdbkit.ext.django.schema import Document, StringProperty,\
    BooleanProperty, DateTimeProperty, IntegerProperty, DocumentSchema, SchemaProperty, DictProperty, ListProperty
from django.utils.safestring import mark_safe
from corehq.apps.appstore.models import Review
from dimagi.utils.timezones import fields as tz_fields
from dimagi.utils.couch.database import get_db
from itertools import chain
from langcodes import langs as all_langs
from collections import defaultdict

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

LICENSES = {
    'public': 'Public Domain',
    'cc': 'Creative Commons Attribution',
    'cc-sa': 'Creative Commons Attribution, Share Alike',
    'cc-nd': 'Creative Commons Attribution, No Derivatives',
    'cc-nc': 'Creative Commons Attribution, Non-Commercial',
    'cc-nc-sa': 'Creative Commons Attribution, Non-Commercial, and Share Alike',
    'cc-nc-nd': 'Creative Commons Attribution, Non-Commercial, and No Derivatives',
    }

def cached_property(method):
    def find_cached(self):
        try:
            return self.cached_properties[method.__name__]
        except KeyError:
            self.cached_properties[method.__name__] = method(self)
            self.save()
            return self.cached_properties[method.__name__]
    return find_cached

class HQBillingAddress(DocumentSchema):
    """
        A billing address for clients
    """
    country = StringProperty()
    postal_code = StringProperty()
    state_province = StringProperty()
    city = StringProperty()
    address = ListProperty()
    name = StringProperty()

    @property
    def html_address(self):
        template = """<address>
            <strong>%(name)s</strong><br />
            %(address)s<br />
            %(city)s%(state)s %(postal_code)s<br />
            %(country)s
        </address>"""
        filtered_address = [a for a in self.address if a]
        address = template % dict(
            name=self.name,
            address="<br />\n".join(filtered_address),
            city=self.city,
            state=", %s" % self.state_province if self.state_province else "",
            postal_code=self.postal_code,
            country=self.country
        )
        return mark_safe(address)

    def update_billing_address(self, **kwargs):
        self.country = kwargs.get('country','')
        self.postal_code = kwargs.get('postal_code','')
        self.state_province = kwargs.get('state_province', '')
        self.city = kwargs.get('city', '')
        self.address = kwargs.get('address', [''])
        self.name = kwargs.get('name', '')


class HQBillingDomainMixin(DocumentSchema):
    """
        This contains all the attributes required to bill a client for CommCare HQ services.
    """
    billing_address = SchemaProperty(HQBillingAddress)
    billing_number = StringProperty()
    currency_code = StringProperty(default=settings.DEFAULT_CURRENCY)

    def update_billing_info(self, **kwargs):
        self.billing_number = kwargs.get('phone_number','')
        self.billing_address.update_billing_address(**kwargs)
        self.currency_code = kwargs.get('currency_code', settings.DEFAULT_CURRENCY)


class Domain(Document, HQBillingDomainMixin):
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
    short_description = StringProperty()
    is_shared = BooleanProperty(default=False)

    # exchange/domain copying stuff
    original_doc = StringProperty()
    original_doc_display_name = StringProperty()
    is_snapshot = BooleanProperty(default=False)
    is_approved = BooleanProperty(default=False)
    snapshot_time = DateTimeProperty()
    published = BooleanProperty(default=False)
    license = StringProperty(choices=LICENSES, default='public')
    title = StringProperty()

    author = StringProperty()
    deployment_date = DateTimeProperty()
    phone_model = StringProperty()
    attribution_notes = StringProperty()

    image_path = StringProperty()
    image_type = StringProperty()

    migrations = SchemaProperty(DomainMigrations)

    cached_properties = DictProperty()

    # to be eliminated from projects and related documents when they are copied for the exchange
    _dirty_fields = ('admin_password', 'admin_password_charset', 'city', 'country', 'region', 'customer_type')

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
    def field_by_prefix(cls, field, prefix='', is_approved=True):
        # unichr(0xfff8) is something close to the highest character available
        res = cls.view("domain/fields_by_prefix",
                                    group=True,
                                    startkey=[field, is_approved, prefix],
                                    endkey=[field, is_approved, "%s%c" % (prefix, unichr(0xfff8)), {}])
        vals = [(d['value'], d['key'][2]) for d in res]
        vals.sort(reverse=True)
        return [(v[1], v[0]) for v in vals]

    @classmethod
    def get_by_field(cls, field, value, is_approved=True):
        return cls.view('domain/fields_by_prefix', key=[field, is_approved, value], reduce=False, include_docs=True).all()

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
        from corehq.apps.app_manager.models import ApplicationBase
        return ApplicationBase.view('app_manager/applications_brief',
                                    startkey=[self.name],
                                    endkey=[self.name, {}]).all()

    def full_applications(self):
        from corehq.apps.app_manager.models import Application, RemoteApp
        WRAPPERS = {'Application': Application, 'RemoteApp': RemoteApp}
        def wrap_application(a):
            return WRAPPERS[a['doc']['doc_type']].wrap(a['doc'])

        return get_db().view('app_manager/applications',
            startkey=[self.name],
            endkey=[self.name, {}],
            include_docs=True,
            wrapper=wrap_application).all()

    @cached_property
    def versions(self):
        apps = self.applications()
        return list(set(a.application_version for a in apps))

    @cached_property
    def has_case_management(self):
        for app in self.full_applications():
            if app.doc_type == 'Application':
                if app.has_case_management():
                    return True
        return False

    @cached_property
    def has_media(self):
        for app in self.full_applications():
            if app.doc_type == 'Application' and app.has_media():
                return True
        return False

    def all_users(self):
        from corehq.apps.users.models import CouchUser
        return CouchUser.by_domain(self.name)

    def has_shared_media(self):
        return False

    def recent_submissions(self):
        res = get_db().view('reports/all_submissions',
            startkey=[self.name, {}],
            endkey=[self.name],
            descending=True,
            reduce=False,
            include_docs=False,
            limit=1).all()
        if len(res) > 0: # if there have been any submissions in the past 30 days
            return datetime.now() <= datetime.strptime(res[0]['value']['time'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(days=30)
        else:
            return False

    @cached_property
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

    def password_format(self):
        """
        This was a performance hit, so for now we'll just return 'a' no matter what
#        If a single application is alphanumeric, return alphanumeric; otherwise, return numeric
        """
#        for app in self.full_applications():
#            if hasattr(app, 'profile'):
#                format = app.profile.get('properties', {}).get('password_format', 'n')
#                if format == 'a':
#                    return 'a'
#        return 'n'
        return 'a'

    @classmethod
    def get_all(cls):
        return Domain.view("domain/not_snapshots",
                            include_docs=True).all()

    def case_sharing_included(self):
        return self.case_sharing or reduce(lambda x, y: x or y, [getattr(app, 'case_sharing', False) for app in self.applications()], False)

    def save_copy(self, new_domain_name=None, user=None):
        from corehq.apps.app_manager.models import get_app
        if new_domain_name is not None and Domain.get_by_name(new_domain_name):
            return None
        db = get_db()

        new_id = db.copy_doc(self.get_id)['id']
        if new_domain_name is None:
            new_domain_name = new_id
        new_domain = Domain.get(new_id)
        new_domain.name = new_domain_name
        new_domain.is_snapshot = False
        new_domain.snapshot_time = None
        new_domain.original_doc = self.name
        new_domain.original_doc_display_name = self.display_name()
        new_domain.organization = None # TODO: use current user's organization (?)

        for field in self._dirty_fields:
            if hasattr(new_domain, field):
                delattr(new_domain, field)

        for res in db.view('domain/related_to_domain', key=[self.name, True]):
            if not self.is_snapshot and res['value']['doc_type'] in ('Application', 'RemoteApp'):
                app = get_app(self.name, res['value']['_id']).get_latest_saved()
                if app:
                    self.copy_component(app.doc_type, app._id, new_domain_name, user=user)
                else:
                    self.copy_component(res['value']['doc_type'], res['value']['_id'], new_domain_name, user=user)
            else:
                self.copy_component(res['value']['doc_type'], res['value']['_id'], new_domain_name, user=user)

        new_domain.save()

        if user:
            user.add_domain_membership(new_domain_name)
            user.save()

        return new_domain

    def copy_component(self, doc_type, id, new_domain_name, user=None):
        from corehq.apps.app_manager.models import import_app
        from corehq.apps.users.models import UserRole
        str_to_cls = {
            'UserRole': UserRole,
            }
        db = get_db()
        if doc_type in ('Application', 'RemoteApp'):
            new_doc = import_app(id, new_domain_name)
        else:
            cls = str_to_cls[doc_type]
            new_id = db.copy_doc(id)['id']

            new_doc = cls.get(new_id)
            for field in self._dirty_fields:
                if hasattr(new_doc, field):
                    delattr(new_doc, field)

            if hasattr(cls, '_meta_fields'):
                for field in cls._meta_fields:
                    if not field.startswith('_') and hasattr(new_doc, field):
                        delattr(new_doc, field)

            new_doc.domain = new_domain_name

        new_doc.original_doc = id

        if self.is_snapshot and doc_type == 'Application':
            new_doc.clean_mapping()

        new_doc.save()
        return new_doc

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
        return Domain.view('domain/snapshots', startkey=[self.name, {}], endkey=[self.name], include_docs=True, descending=True)

    def published_snapshot(self):
        snapshots = self.snapshots().all()
        for snapshot in snapshots:
            if snapshot.published:
                return snapshot
        if len(snapshots) > 0:
            return snapshots[0]
        else:
            return None

    @classmethod
    def published_snapshots(cls, include_unapproved=False, page=None, per_page=10):
        skip = None
        limit = None
        if page:
            skip = (page - 1) * per_page
            limit = per_page
        if include_unapproved:
            return cls.view('domain/published_snapshots', startkey=[False, {}], include_docs=True, descending=True, limit=limit, skip=skip)
        else:
            return cls.view('domain/published_snapshots', endkey=[True], include_docs=True, descending=True, limit=limit, skip=skip)

    @classmethod
    def snapshot_search(cls, query, page=None, per_page=10):
        skip = None
        limit = None
        if page:
            skip = (page - 1) * per_page
            limit = per_page
        results = get_db().search('domain/snapshot_search', q=json.dumps(query), limit=limit, skip=skip, stale=ok)
        return map(cls.get, [r['id'] for r in results]), results.total_rows

    def organization_doc(self):
        from corehq.apps.orgs.models import Organization
        return Organization.get_by_name(self.organization)

    def organization_title(self):
        if self.organization:
            return self.organization_doc().title
        else:
            return ''

    def display_name(self):
        if self.is_snapshot:
            return "Snapshot of %s" % self.copied_from().display_name()
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

    def get_license_display(self):
        return LICENSES.get(self.license)

    def copies(self):
        return Domain.view('domain/copied_from_snapshot', key=self.name, include_docs=True)

    def copies_of_parent(self):
        return Domain.view('domain/copied_from_snapshot', keys=[s.name for s in self.copied_from().snapshots()], include_docs=True)

    def delete(self):
        # delete all associated objects
        db = get_db()
        related_docs = db.view('domain/related_to_domain', startkey=[self.name], endkey=[self.name, {}], include_docs=True)
        for doc in related_docs:
            db.delete_doc(doc['doc'])
        super(Domain, self).delete()

    def all_media(self):
        from corehq.apps.hqmedia.models import CommCareMultimedia
        return CommCareMultimedia.view('hqmedia/by_domain', key=self.name, include_docs=True).all()

    @classmethod
    def popular_sort(cls, domains, page):
        sorted_list = []
        MIN_REVIEWS = 1.0

        domains = [(domain, Review.get_average_rating_by_app(domain.original_doc), Review.get_num_ratings_by_app(domain.original_doc)) for domain in domains]
        domains = [(domain, avg or 0.0, num or 0) for domain, avg, num in domains]

        total_average_sum = sum(avg for domain, avg, num in domains)
        total_average_count = len(domains)
        if not total_average_count:
            return []
        total_average = (total_average_sum / total_average_count)

        for domain, average_rating, num_ratings in domains:
            if num_ratings == 0:
                sorted_list.append((0.0, domain))
            else:
                weighted_rating = ((num_ratings / (num_ratings + MIN_REVIEWS)) * average_rating + (MIN_REVIEWS / (num_ratings + MIN_REVIEWS)) * total_average)
                sorted_list.append((weighted_rating, domain))

        sorted_list = [domain for weighted_rating, domain in sorted(sorted_list, key=lambda domain: domain[0], reverse=True)]

        return sorted_list[((page-1)*9):((page)*9)]

    @classmethod
    def hit_sort(cls, domains, page):
        domains = list(domains)
        domains = sorted(domains, key=lambda domain: len(domain.copies_of_parent()), reverse=True)
        return domains[((page-1)*9):((page)*9)]


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

class DomainCounter(Document):
    domain = StringProperty()
    name = StringProperty()
    count = IntegerProperty()
    
    @classmethod
    def get_or_create(cls, domain, name):
        #TODO: Need to make this atomic
        counter = cls.view("domain/counter",
            key = [domain, name],
            include_docs=True
        ).one()
        if counter is None:
            counter = DomainCounter (
                domain = domain,
                name = name,
                count = 0
            )
            counter.save()
        return counter
    
    @classmethod
    def increment(cls, domain, name, amount=1):
        num_tries = 0
        while True:
            try:
                counter = cls.get_or_create(domain, name)
                range_start = counter.count + 1
                counter.count += amount
                counter.save()
                range_end = counter.count
                break
            except ResourceConflict:
                num_tries += 1
                if num_tries >= 500:
                    raise
        return (range_start, range_end)

