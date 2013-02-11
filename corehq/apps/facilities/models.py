from couchdbkit.ext.django.schema import *
import freddy
import datetime
import pytz

from corehq.apps.users.models import CouchUser

def utcnow():
    return datetime.datetime.utcnow().replace(tzinfo=pytz.utc)


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

    created_at = DateTimeProperty()
    synced_at = DateTimeProperty(
        verbose_name="Time of last full sync of facilities for this registry")
    syncing = BooleanProperty()
    last_sync_failed = BooleanProperty(default=True)

    @classmethod
    def all(cls):
        return cls.view('facilities/all_registries', reduce=False,
            include_docs=True).all()

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
            raise ValueError()

        try:
            ours_existing = {}
            self.syncing = True

            for our_f in Facility.by_registry(self._id).all():
                if our_f.synced_at:
                    local_id = unicode(our_f.data['id'])
                    ours_existing[local_id] = our_f
                else:
                    # new local facility
                    f.save(update_remote=True)

            for their_f in self.remote_registry.facilities.all():
                remote_id = unicode(their_f['id'])
                if remote_id in ours_existing:
                    if strategy == 'theirs':
                        ours = ours_existing[remote_id]
                        ours.data = their_f.to_dict()
                        ours.save(update_remote=False)
                    else:  # strategy == 'ours'
                        for f, v in ours.data.items():
                            their_f[f] = v
                        their_f.save()
                else:
                    # new remote facility
                    now = utcnow()
                    our_new_f = Facility(registry_id=self._id,
                        data=their_f.to_dict(), synced_at=now,
                        sync_attempted_at=now)
                    our_new_f.save(update_remote=False)

            self.synced_at = utcnow()

        except Exception:
            self.last_sync_failed = True
            raise

        else:
            self.last_sync_failed = False

        finally:
            self.syncing = False
            self.save()

    def save(self, *args, **kwargs):
        # todo: test validitiy
        self.remote_registry

        if self._id is None:
            self.created_at = utcnow()

        return super(FacilityRegistry, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Delete associated facilities"""

        for f in Facility.by_registry(self._id):
            f.delete(delete_remote=False)

        return super(FacilityRegistry, self).delete(*args, **kwargs)


class Facility(Document):
    registry_id = StringProperty()
    data = DictProperty(
        verbose_name="Raw properties from the facility registry")
    synced_at = DateTimeProperty(
        verbose_name="Time of last successful (individual) sync "
                     "with the facility registry")
    sync_attempted_at = DateTimeProperty(
        verbose_name="Time of last attempted sync with the facility registry")

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
        core_properties = self.data or {}
        print "core_properties", core_properties
        extended_properties = core_properties.pop('properties', {})

        return freddy.Facility(
            is_new=not self.synced_at, registry=self.registry.remote_registry,
            properties=extended_properties, **core_properties)

    def delete(self, delete_remote=False, *args, **kwargs):
        if delete_remote:
            self.remote_facility.delete()

        return super(Facility, self).delete(*args, **kwargs)

    def save(self, update_remote=True, *args, **kwargs):
        now = utcnow()
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
