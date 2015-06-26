from dimagi.ext.couchdbkit import *
import freddy
import datetime
import copy


def clean_data(data):
    """
    Ensure tzinfo.utcoffset() == None (use UTC implicitly) so the
    following doesn't happen:
    
    1. Save ISO8601 representation of a time with an offset (+HH:MM) as
       a string value in a DictProperty.
    2. That string matches couchdbkit's datetime regex, so it gets
       wrapped as a DateTimeProperty.
    3. couchdbkit appends 'Z' when the string representation is
       requested, leading to an invalid +HH:MMZ format.
    
    """
    for k, v in data.items():
        if isinstance(v, datetime.datetime):
            data[k] = (v - v.utcoffset()).replace(tzinfo=None)
        if isinstance(v, dict):
            data[k] = clean_data(v)

    return data


VERSION_CHOICES = (
    ('1.0', '1.0'),
    ('1.1', '1.1')
)


class FacilityRegistry(Document):
    url = StringProperty(
        verbose_name="Endpoint url, including any version component")
    username = StringProperty(
        verbose_name="username for HTTP Basic Authentication")
    password = StringProperty(
        verbose_name="password for HTTP Basic Authentication")
    version = StringProperty(
        verbose_name="Version as a list, e.g. [1, 1] for 1.1")
    name = StringProperty(
        verbose_name="Name/description of the facility registry")

    domain = StringProperty()
    created_at = DateTimeProperty()
    synced_at = DateTimeProperty(
        verbose_name="Time of last full sync of facilities for this registry")
    syncing = BooleanProperty()
    last_sync_failed = BooleanProperty(default=True)

    def get_facilities(self):
        return Facility.by_registry(self._id)

    @classmethod
    def get(cls, id, domain=None, *args, **kwargs):
        registry = super(FacilityRegistry, cls).get(id, *args, **kwargs)
        if domain is not None:
            assert registry.domain == domain
        return registry

    @classmethod
    def by_domain(cls, domain):
        from corehq.apps.facilities.dbaccessors import \
            get_facility_registries_in_domain
        return get_facility_registries_in_domain(domain)

    @property
    def remote_registry(self):
        return freddy.Registry(
            self.url, username=self.username, password=self.password)

    def sync_with_remote(self, strategy='theirs'):
        """
        Sync local facilities with remote facilities.

        All new local facilities get sent to the server, all new remote
        facilities get saved locally.  Conflict resolution between existing
        facilities is nonexistent: if strategy is 'theirs', all existing local
        facilities are overwritten with remote data, and vice versa if strategy
        is 'ours'.

        """
        if strategy not in ('ours', 'theirs'):
            raise ValueError("Invalid facility sync strategy.")

        try:
            ours_existing = {}
            self.syncing = True
            self.save()

            for our_f in Facility.by_registry(self._id).all():
                if our_f.synced_at:
                    local_id = unicode(our_f.data['uuid'])
                    ours_existing[local_id] = our_f
                else:
                    # new local facility
                    f.save(update_remote=True)

            for their_f in self.remote_registry.facilities.all():
                remote_id = unicode(their_f['uuid'])
                data = clean_data(their_f.to_dict())

                if remote_id in ours_existing:
                    if strategy == 'theirs':
                        ours = ours_existing[remote_id]
                        ours.data = data
                        ours.save(update_remote=False)
                    else:  # strategy == 'ours'
                        for f, v in ours.data.items():
                            their_f[f] = v
                        their_f.save()
                else:
                    # new remote facility
                    now = datetime.datetime.utcnow()
                    our_new_f = Facility(registry_id=self._id,
                        domain=self.domain, data=data, synced_at=now,
                        sync_attempted_at=now)

                    our_new_f.save(update_remote=False)

            self.synced_at = datetime.datetime.utcnow()

        except Exception:
            self.last_sync_failed = True
            raise

        else:
            self.last_sync_failed = False

        finally:
            self.syncing = False
            self.save()

    def save(self, *args, **kwargs):
        # todo: test validity
        self.remote_registry

        if self._id is None:
            self.created_at = datetime.datetime.utcnow()

        return super(FacilityRegistry, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Delete associated facilities"""

        for f in Facility.by_registry(self._id):
            f.delete(delete_remote=False)

        return super(FacilityRegistry, self).delete(*args, **kwargs)


class Facility(Document):
    registry_id = StringProperty()
    # denormalized for purpose of permissions checking
    domain = StringProperty()
    data = DictProperty(
        verbose_name="Raw properties from the facility registry")
    synced_at = DateTimeProperty(
        verbose_name="Time of last successful (individual) sync "
                     "with the facility registry")
    sync_attempted_at = DateTimeProperty(
        verbose_name="Time of last attempted sync with the facility registry")

    @classmethod
    def get(cls, id, domain=None, *args, **kwargs):
        facility = super(Facility, cls).get(id, *args, **kwargs)
        if domain is not None:
            assert facility.domain == domain
        return facility

    @classmethod
    def by_registry(cls, registry_id=None):
        if registry_id:
            kwargs = {'key': registry_id}
        else:
            kwargs = {'startkey': [], 'endkey': [{}]}

        return cls.view('facilities/facilities_by_registry', reduce=False,
            include_docs=True, **kwargs)

    @property
    def registry(self):
        if self.registry_id:
            return FacilityRegistry.get(self.registry_id)
        else:
            return None

    @property
    def remote_facility(self):
        core_properties = dict(copy.deepcopy(self.data)) if self.data else {}
        extended_properties = core_properties.pop('properties', {})

        return freddy.Facility(
            new=not self.synced_at, registry=self.registry.remote_registry,
            properties=extended_properties, **core_properties)

    def delete(self, delete_remote=False, *args, **kwargs):
        if delete_remote:
            self.remote_facility.delete()

        return super(Facility, self).delete(*args, **kwargs)

    def save(self, update_remote=True, *args, **kwargs):
        now = datetime.datetime.utcnow()
        self.sync_attempted_at = now

        try:
            if update_remote:
                self.remote_facility.save()
        except Exception:
            raise
        else:
            if update_remote:
                self.synced_at = now
        finally:
            return super(Facility, self).save(*args, **kwargs)
