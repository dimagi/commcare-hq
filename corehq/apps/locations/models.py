import uuid
from datetime import datetime
from functools import partial

from django.db import models, transaction
from django.db.models import Q

import jsonfield
from django_bulk_update.helper import bulk_update as bulk_update_helper
from django_cte import CTEQuerySet
from memoized import memoized

from corehq.apps.domain.models import Domain
from corehq.apps.locations.adjacencylist import AdjListManager, AdjListModel
from corehq.apps.products.models import SQLProduct
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.interfaces.supply import SupplyInterface


class LocationTypeManager(models.Manager):

    def full_hierarchy(self, domain):
        """
        Returns a graph of the form
        {
           '<loc_type_id>: (
               loc_type,
               {'<child_loc_type_id>': (child_loc_type, [...])}
           )
        }
        """
        hierarchy = {}

        def insert_loc_type(loc_type):
            """
            Get parent location's hierarchy, insert loc_type into it, and return
            hierarchy below loc_type
            """
            if not loc_type.parent_type:
                lt_hierarchy = hierarchy
            else:
                lt_hierarchy = insert_loc_type(loc_type.parent_type)
            if loc_type.id not in lt_hierarchy:
                lt_hierarchy[loc_type.id] = (loc_type, {})
            return lt_hierarchy[loc_type.id][1]

        for loc_type in self.filter(domain=domain).all():
            insert_loc_type(loc_type)

        return hierarchy

    def by_domain(self, domain):
        """
        Sorts location types by hierarchy
        """
        ordered_loc_types = []

        def step_through_graph(hierarchy):
            for _, (loc_type, children) in hierarchy.items():
                ordered_loc_types.append(loc_type)
                step_through_graph(children)

        step_through_graph(self.full_hierarchy(domain))
        return ordered_loc_types


StockLevelField = partial(models.DecimalField, max_digits=10, decimal_places=1)


@memoized
def stock_level_config_for_domain(domain, commtrack_enabled):
    if not commtrack_enabled:
        return None
    from corehq.apps.commtrack.models import CommtrackConfig
    ct_config = CommtrackConfig.for_domain(domain)
    if ct_config is None or not hasattr(ct_config, 'stocklevelsconfig'):
        return None
    else:
        return ct_config.stocklevelsconfig


class LocationType(models.Model):
    domain = models.CharField(max_length=255, db_index=True)
    name = models.CharField(max_length=255)
    code = models.SlugField(db_index=False, null=True)
    parent_type = models.ForeignKey('self', null=True, on_delete=models.CASCADE)
    administrative = models.BooleanField(default=False)
    shares_cases = models.BooleanField(default=False)
    view_descendants = models.BooleanField(default=False)

    # Sync optimization controls
    _expand_from = models.ForeignKey(
        'self',
        null=True,
        related_name='+',
        db_column='expand_from',
        on_delete=models.CASCADE,
    )  # levels below this location type that we start expanding from
    _expand_from_root = models.BooleanField(default=False, db_column='expand_from_root')
    expand_to = models.ForeignKey(
        "self",
        null=True,
        related_name="+",
        on_delete=models.CASCADE,
    )  # levels above this type that are synced
    include_without_expanding = models.ForeignKey(
        'self',
        null=True,
        related_name='+',
        on_delete=models.SET_NULL,
    )  # include all levels of this type and their ancestors
    # If specified, include only the linked types
    include_only = models.ManyToManyField('self', symmetrical=False, related_name='included_in')

    last_modified = models.DateTimeField(auto_now=True, db_index=True)
    has_user = models.BooleanField(default=False)

    emergency_level = StockLevelField(default=0.5)
    understock_threshold = StockLevelField(default=1.5)
    overstock_threshold = StockLevelField(default=3.0)

    objects = LocationTypeManager()

    class Meta(object):
        app_label = 'locations'
        unique_together = (
            ('domain', 'code'),
            ('domain', 'name'),
        )

    def __init__(self, *args, **kwargs):
        super(LocationType, self).__init__(*args, **kwargs)
        self._administrative_old = self.administrative

    @property
    def expand_from(self):
        return self._expand_from

    @expand_from.setter
    def expand_from(self, value):
        if self._expand_from_root is True:
            self._expand_from_root = False
        self._expand_from = value

    @property
    def expand_from_root(self):
        return self._expand_from_root

    @expand_from_root.setter
    def expand_from_root(self, value):
        if self._expand_from_root is False and value is True:
            self._expand_from = None
        self._expand_from_root = value

    @property
    @memoized
    def commtrack_enabled(self):
        return Domain.get_by_name(self.domain).commtrack_enabled

    def _populate_stock_levels(self, config, update_fields=None):
        self.emergency_level = config.emergency_level
        self.understock_threshold = config.understock_threshold
        self.overstock_threshold = config.overstock_threshold
        if update_fields is not None:
            update_fields.extend(['emergency_level', 'understock_threshold', 'overstock_threshold'])

    def save(self, *args, **kwargs):
        additional_update_fields = []
        if not self.code:
            from corehq.apps.commtrack.util import unicode_slug
            self.code = unicode_slug(self.name)
            additional_update_fields.append('code')
        if not self.commtrack_enabled:
            self.administrative = True
            additional_update_fields.append('administrative')

        config = stock_level_config_for_domain(self.domain, self.commtrack_enabled)
        if config:
            self._populate_stock_levels(config, update_fields=additional_update_fields)

        is_not_first_save = self.pk is not None
        if kwargs.get('update_fields') is not None:
            kwargs['update_fields'].extend(additional_update_fields)
        super(LocationType, self).save(*args, **kwargs)

        if is_not_first_save:
            self.sync_administrative_status()

    def sync_administrative_status(self, sync_supply_points=True):
        from .tasks import sync_administrative_status
        if self._administrative_old != self.administrative:
            if sync_supply_points:
                sync_administrative_status.delay(self)
            self._administrative_old = self.administrative

    def __str__(self):
        return self.name

    def __repr__(self):
        return "LocationType(domain='{}', name='{}', administrative={})".format(
            self.domain,
            self.name,
            self.administrative,
        )

    @property
    @memoized
    def can_have_children(self):
        return LocationType.objects.filter(parent_type=self).exists()

    @classmethod
    def _pre_bulk_save(cls, objects):
        if not objects:
            return

        commtrack_enabled = objects[0].commtrack_enabled
        if not commtrack_enabled:
            for o in objects:
                o.administrative = True

        domain = objects[0].domain
        stock_config = stock_level_config_for_domain(domain, commtrack_enabled)
        if stock_config:
            for o in objects:
                o._populate_stock_levels(stock_config)

    @classmethod
    def bulk_create(cls, objects):
        # 'objects' is a list of new LocationType objects to be created
        if not objects:
            return []

        cls._pre_bulk_save(objects)
        cls.objects.bulk_create(objects)
        return list(objects)

    @classmethod
    def bulk_update(cls, objects):
        # 'objects' is a list of existing LocationType objects to be updated
        # Note: this is tightly coupled with .bulk_management.NewLocationImporter.bulk_commit()
        #       so it can't be used on its own
        cls._pre_bulk_save(objects)
        now = datetime.utcnow()
        for o in objects:
            o.last_modified = now
        # the caller should call 'sync_administrative_status' for individual objects
        bulk_update_helper(objects)

    @classmethod
    def bulk_delete(cls, objects):
        # Given a list of existing SQL objects, bulk delete them
        if not objects:
            return
        ids = [o.id for o in objects]
        cls.objects.filter(id__in=ids).delete()


class LocationQueriesMixin(object):

    def location_ids(self):
        return self.values_list('location_id', flat=True)

    def accessible_to_user(self, domain, user):
        if user.has_permission(domain, 'access_all_locations'):
            return self.filter(domain=domain)

        assigned_location_ids = user.get_location_ids(domain)
        if not assigned_location_ids:
            return self.none()  # No locations are assigned to this user

        return SQLLocation.objects.get_locations_and_children(assigned_location_ids)

    def delete(self, *args, **kwargs):
        from .document_store import publish_location_saved
        for domain, location_id in self.values_list('domain', 'location_id'):
            publish_location_saved(domain, location_id, is_deletion=True)
        return super(LocationQueriesMixin, self).delete(*args, **kwargs)


class LocationQuerySet(LocationQueriesMixin, CTEQuerySet):

    def accessible_to_user(self, domain, user):
        ids_query = super(LocationQuerySet, self).accessible_to_user(domain, user)
        return self.filter(id__in=ids_query)


class LocationManager(LocationQueriesMixin, AdjListManager):

    def get_or_None(self, **kwargs):
        try:
            return self.get(**kwargs)
        except SQLLocation.DoesNotExist:
            return None

    def get_queryset(self):
        return LocationQuerySet(self.model, using=self._db)

    def get_from_user_input(self, domain, user_input):
        """
        First check by site-code, if that fails, fall back to name.
        Note that name lookup may raise MultipleObjectsReturned.
        """
        try:
            return self.get(domain=domain, site_code=user_input)
        except self.model.DoesNotExist:
            return self.get(domain=domain, name__iexact=user_input)

    def filter_by_user_input(self, domain, user_input):
        """
        Returns a queryset based on user input
          - Matching happens by name or site-code
          - Adding a slash to the input string starts a new search node among descendants
          - Matching is partial unless the query node is wrapped in quotes
        Refer to TestFilterByUserInput for example usages.
        """
        query = None
        for part in user_input.split('/'):
            query = self.get_queryset_descendants(query) if query is not None else self
            if part:
                if part.startswith('"') and part.endswith('"'):
                    query = query.filter(name__iexact=part[1:-1])
                else:
                    part = part.lstrip('"')
                    query = query.filter(
                        Q(name__icontains=part) | Q(site_code__icontains=part)
                    )
        return query

    def get_locations(self, location_ids):
        return self.filter(location_id__in=location_ids)

    def get_locations_and_children(self, location_ids):
        """
        Takes a set of location ids and returns a django queryset of those
        locations and their children.
        """
        locations = self.filter(location_id__in=location_ids)
        return self.get_queryset_descendants(locations, include_self=True)

    def get_locations_and_children_ids(self, location_ids):
        return list(self.get_locations_and_children(location_ids).location_ids())


class OnlyUnarchivedLocationManager(LocationManager):

    def get_queryset(self):
        return (super(OnlyUnarchivedLocationManager, self).get_queryset()
                .filter(is_archived=False))

    def accessible_location_ids(self, domain, user):
        return list(self.accessible_to_user(domain, user).location_ids())


class SQLLocation(AdjListModel):
    domain = models.CharField(max_length=255, db_index=True)
    name = models.CharField(max_length=255, null=True)
    location_id = models.CharField(max_length=100, db_index=True, unique=True)
    location_type = models.ForeignKey(LocationType, on_delete=models.CASCADE)
    site_code = models.CharField(max_length=255)
    external_id = models.CharField(max_length=255, null=True, blank=True)
    metadata = jsonfield.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True, db_index=True)
    is_archived = models.BooleanField(default=False)
    archived_on = models.DateTimeField(null=True, blank=True)
    latitude = models.DecimalField(max_digits=20, decimal_places=10, null=True, blank=True)
    longitude = models.DecimalField(max_digits=20, decimal_places=10, null=True, blank=True)
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children', on_delete=models.CASCADE)

    # Use getter and setter below to access this value
    # since stocks_all_products can cause an empty list to
    # be what is stored for a location that actually has
    # all products available.
    _products = models.ManyToManyField(SQLProduct)
    stocks_all_products = models.BooleanField(default=True)

    supply_point_id = models.CharField(max_length=255, db_index=True, unique=True, null=True, blank=True)

    # No longer used. Should be removed once all references have been tracked down and removed
    user_id = models.CharField(max_length=255, blank=True)

    objects = _tree_manager = LocationManager()
    # This should really be the default location manager
    active_objects = OnlyUnarchivedLocationManager()

    def get_ancestor_of_type(self, type_code):
        """
        Returns the ancestor of given location_type_code of the location
        """
        try:
            return self.get_ancestors().get(location_type__code=type_code)
        except self.DoesNotExist:
            return None

    @classmethod
    def get_sync_fields(cls):
        return ["domain", "name", "site_code", "external_id",
                "metadata", "is_archived"]

    def save(self, *args, **kwargs):
        from corehq.apps.commtrack.models import sync_supply_point
        from .document_store import publish_location_saved

        additional_update_fields = []
        if not self.location_id:
            self.location_id = uuid.uuid4().hex
            additional_update_fields.append('location_id')

        with transaction.atomic():
            set_site_code_if_needed(self, update_fields=additional_update_fields)
            sync_supply_point(self, update_fields=additional_update_fields)
            if kwargs.get('update_fields') is not None:
                kwargs['update_fields'].extend(additional_update_fields)
            super(SQLLocation, self).save(*args, **kwargs)

        publish_location_saved(self.domain, self.location_id)

    def delete(self, *args, **kwargs):
        """Delete this location and all descentants

        Supply point cases and user updates are performed asynchronously.
        """
        from .tasks import update_users_at_locations, delete_locations_related_rules
        from .document_store import publish_location_saved

        to_delete = self.get_descendants(include_self=True)
        for loc in to_delete:
            loc._remove_user()

        super(SQLLocation, self).delete(*args, **kwargs)
        update_users_at_locations.delay(
            self.domain,
            [loc.location_id for loc in to_delete],
            [loc.supply_point_id for loc in to_delete if loc.supply_point_id],
            list(self.get_ancestors().location_ids()),
        )
        for loc in to_delete:
            publish_location_saved(loc.domain, loc.location_id, is_deletion=True)

        delete_locations_related_rules.delay([loc.location_id for loc in to_delete])

    full_delete = delete

    def get_descendants(self, include_self=False, **kwargs):
        if include_self:
            where = Q(domain=self.domain, id=self.id)
        else:
            where = Q(domain=self.domain, parent_id=self.id)
        return SQLLocation.objects.get_descendants(
            where, **kwargs
        )

    def get_ancestors(self, include_self=False, **kwargs):
        where = Q(domain=self.domain, id=self.id if include_self else self.parent_id)
        return SQLLocation.objects.get_ancestors(
            where, **kwargs
        )

    @classmethod
    def bulk_delete(cls, locations, ancestor_location_ids):
        """Bulk delete the given locations and update their ancestors

        WARNING databases may be left in an inconsistent state if the
        transaction in which this deletion is performed is rolled back.
        This method mutates other databases that will not be reverted on
        transaction rollback.

        :param locations: A list of SQLLocation objects. All locations
        in the list are expected to be leaf nodes or parents of nodes
        that are also in the list. Behavior of passing a non-leaf node
        without also passing all of its descendants is undefined.
        :param ancestor_location_ids: A list of ancestor `location_id`s
        for the given `locations`.
        """
        from .tasks import update_users_at_locations
        from .document_store import publish_location_saved

        if not locations:
            return
        if len(set(loc.domain for loc in locations)) != 1:
            raise ValueError("cannot bulk delete locations for multiple domains")
        cls.objects.filter(id__in=[loc.id for loc in locations]).delete()
        # NOTE _remove_user() not called here. No domains were using
        # SQLLocation.user_id at the time this was written, and that
        # field is slated for removal.
        update_users_at_locations.delay(
            locations[0].domain,
            [loc.location_id for loc in locations],
            [loc.supply_point_id for loc in locations if loc.supply_point_id],
            ancestor_location_ids,
        )
        for loc in locations:
            publish_location_saved(loc.domain, loc.location_id, is_deletion=True)

    def to_json(self, include_lineage=True):
        json_dict = {
            'name': self.name,
            'site_code': self.site_code,
            '_id': self.location_id,
            'location_id': self.location_id,
            'doc_type': 'Location',
            'domain': self.domain,
            'external_id': self.external_id,
            'is_archived': self.is_archived,
            'archived_on': self.archived_on.isoformat() if self.archived_on else None,
            'last_modified': self.last_modified.isoformat(),
            'latitude': float(self.latitude) if self.latitude else None,
            'longitude': float(self.longitude) if self.longitude else None,
            'metadata': self.metadata,
            'location_type': self.location_type.name,
            'location_type_code': self.location_type.code,
            'parent_location_id': self.parent_location_id,
        }
        if include_lineage:
            # lineage requires a non-trivial db hit
            json_dict['lineage'] = self.lineage
        return json_dict

    @property
    def lineage(self):
        return list(reversed(self.path[:-1]))

    _id = property(lambda self: self.location_id)
    get_id = property(lambda self: self.location_id)

    @property
    def products(self):
        """
        If there are no products specified for this location, assume all
        products for the domain are relevant.
        """
        if self.stocks_all_products:
            return SQLProduct.by_domain(self.domain)
        else:
            return self._products.all()

    @products.setter
    def products(self, value):
        # this will set stocks_all_products to true if the user
        # has added all products in the domain to this location
        self.stocks_all_products = set(value) == set(SQLProduct.by_domain(self.domain))

        self._products.set(value)

    def _remove_user(self):
        """
        Unassigns the users assigned to that location.

        Used by both archive and delete methods
        """
        if self.user_id:
            from corehq.apps.users.models import CommCareUser
            user = CommCareUser.get(self.user_id)
            user.active = False
            user.save()

    def archive(self):
        """
        Mark a location and its descendants as archived and unassigns users
        assigned to the location.
        """
        from .tasks import update_users_at_locations
        locations = self.get_descendants(include_self=True)
        for loc in locations:
            loc.is_archived = True
            loc.archived_on = datetime.utcnow()
            loc.save()
            loc._remove_user()

        update_users_at_locations.delay(
            self.domain,
            [loc.location_id for loc in locations],
            [loc.supply_point_id for loc in locations if loc.supply_point_id],
            list(self.get_ancestors().location_ids()),
        )

    def unarchive(self):
        """
        Unarchive a location and reopen supply point case if it
        exists.
        """
        import itertools
        from corehq.apps.users.models import CommCareUser
        for loc in itertools.chain(self.get_descendants(include_self=True), self.get_ancestors()):
            loc.is_archived = False
            loc.archived_on = None
            loc.save()

            if loc.user_id:
                user = CommCareUser.get(loc.user_id)
                user.active = True
                user.save()

    class Meta(object):
        app_label = 'locations'
        unique_together = ('domain', 'site_code',)

    def __str__(self):
        return "{} ({})".format(self.name, self.domain)

    def __repr__(self):
        return "SQLLocation(domain='{}', name='{}', location_type='{}')".format(
            self.domain,
            self.name,
            self.location_type.name if hasattr(self, 'location_type') else None,
        )

    @property
    def display_name(self):
        return "{} [{}]".format(self.name, self.location_type.name)

    def archived_descendants(self):
        """
        Returns a list of archived descendants for this location.
        """
        return self.get_descendants().filter(is_archived=True)

    def child_locations(self, include_archive_ancestors=False):
        """
        Returns a list of this location's children.
        """
        children = self.get_children()
        return filter_for_archived(children, include_archive_ancestors)

    @classmethod
    def root_locations(cls, domain, include_archive_ancestors=False):
        roots = cls.objects.root_nodes().filter(domain=domain)
        return filter_for_archived(roots, include_archive_ancestors)

    def get_path_display(self):
        return '/'.join(self.get_ancestors(include_self=True)
                            .values_list('name', flat=True))

    def case_sharing_group_object(self, user_id=None):
        """
        Returns a fake group object that cannot be saved.

        This is used for giving users access via case sharing groups, without
        having a real group for every location that we have to manage/hide.
        """
        from corehq.apps.groups.models import UnsavableGroup

        group = UnsavableGroup(
            domain=self.domain,
            users=[user_id] if user_id else [],
            last_modified=datetime.utcnow(),
            name=self.get_path_display() + '-Cases',
            _id=self.location_id,
            case_sharing=True,
            reporting=False,
            metadata={
                'commcare_location_type': self.location_type.name,
                'commcare_location_name': self.name,
            },
        )

        for key, val in self.metadata.items():
            group.metadata['commcare_location_' + key] = val

        return group

    def is_direct_ancestor_of(self, location):
        return (location.get_ancestors(include_self=True)
                .filter(pk=self.pk).exists())

    def descendants_include_location(self, location_id):
        return (
            self.get_descendants(include_self=True)
            .filter(location_id=location_id)
            .exists()
        )

    @classmethod
    def by_domain(cls, domain):
        return cls.objects.filter(domain=domain)

    @property
    def path(self):
        try:
            return self._path
        except AttributeError:
            self._path = list(self.get_ancestors(include_self=True).location_ids())
        return self._path

    @path.setter
    def path(self, value):
        self._path = value

    @classmethod
    def by_location_id(cls, location_id):
        try:
            return cls.objects.get(location_id=location_id)
        except cls.DoesNotExist:
            return None

    # For quick_find compatability
    by_id = by_location_id

    def linked_supply_point(self):
        if not self.supply_point_id:
            return None
        try:
            return SupplyInterface(self.domain).get_supply_point(self.supply_point_id)
        except CaseNotFound:
            return None

    @property
    def parent_location_id(self):
        return self.parent.location_id if self.parent else None

    @property
    def location_type_name(self):
        return self.location_type.name

    @property
    def sql_location(self):
        # For backwards compatability
        return self


def filter_for_archived(locations, include_archive_ancestors):
    """
    Perform filtering on a location queryset.

    include_archive_ancestors toggles between selecting only active
    children and selecting any child that is archived or has
    archived descendants.
    """
    if include_archive_ancestors:
        return [
            item for item in locations
            if item.is_archived or item.archived_descendants()
        ]
    else:
        return locations.filter(is_archived=False)


def make_location(**kwargs):
    """API compatabile with `Location.__init__`, but returns a SQLLocation"""
    loc_type_name = kwargs.pop('location_type')
    try:
        sql_location_type = LocationType.objects.get(
            domain=kwargs['domain'],
            name=loc_type_name,
        )
    except LocationType.DoesNotExist:
        msg = "You can't create a location without a real location type"
        raise LocationType.DoesNotExist(msg)
    kwargs['location_type'] = sql_location_type
    parent = kwargs.pop('parent', None)
    kwargs['parent'] = parent.sql_location if parent else None
    return SQLLocation(**kwargs)


def get_location(location_id, domain=None):
    """Drop-in replacement for `Location.get`, but returns a SQLLocation"""
    if domain:
        return SQLLocation.objects.get(domain=domain, location_id=location_id)
    else:
        return SQLLocation.objects.get(location_id=location_id)


def set_site_code_if_needed(location, update_fields=None):
    from corehq.apps.commtrack.util import generate_code
    if not location.site_code:
        all_codes = [
            code.lower() for code in
            (SQLLocation.objects.exclude(location_id=location.location_id)
                                .filter(domain=location.domain)
                                .values_list('site_code', flat=True))
        ]
        location.site_code = generate_code(location.name, all_codes)
        if update_fields is not None:
            update_fields.append('site_code')


class LocationFixtureConfiguration(models.Model):
    domain = models.CharField(primary_key=True, max_length=255)
    sync_flat_fixture = models.BooleanField(default=True)
    sync_hierarchical_fixture = models.BooleanField(default=True)

    def __repr__(self):
        return '{}: flat: {}, hierarchical: {}'.format(
            self.domain, self.sync_flat_fixture, self.sync_hierarchical_fixture
        )

    @classmethod
    def for_domain(cls, domain):
        try:
            return cls.objects.get(domain=domain)
        except cls.DoesNotExist:
            return cls(domain=domain)


def get_domain_locations(domain):
    return SQLLocation.active_objects.filter(domain=domain)
