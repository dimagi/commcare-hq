from datetime import timedelta
from dimagi.utils.couch.delete import delete
from dimagi.utils.couch.safe_index import safe_index
from couchdbkit.ext.django.schema import DateTimeProperty, DocumentSchema
from couchdbkit.exceptions import ResourceConflict

LOCK_EXPIRATION = timedelta(hours = 1)

class LockableMixIn(DocumentSchema):
    lock_date = DateTimeProperty()

    def acquire_lock(self, now):
        """
        Returns True if the lock was acquired by the calling thread, 
        False if another thread acquired it first
        """
        if (self.lock_date is None) or (now > (self.lock_date + LOCK_EXPIRATION)):
            try:
                self.lock_date = now
                self.save()
                return True
            except ResourceConflict:
                return False
        else:
            return False

    def release_lock(self):
        assert self.lock_date is not None
        self.lock_date = None
        self.save()