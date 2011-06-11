from dimagi.utils.mixins import UnicodeMixIn
from couchdbkit.resource import ResourceNotFound

class Change(UnicodeMixIn):
    """
    Represents a single line from the _changes feed, for easier processing
    """
    
    def __init__(self, line):
        self.line = line
        self.id = line.get("id", None)
        self.seq = line.get("seq", None)
        self.changes = line.get("changes", [])
        self.deleted = "deleted" in line and line["deleted"]
        
    @property
    def rev(self):
        if self.changes and self.changes[0] and "rev" in self.changes[0]:
            return self.changes[0]["rev"]
        return None
    
    def __unicode__(self):
        return str(self.line)
    
    
    def is_current(self, db):
        """Is this change pointing at the current rev in the DB?"""
        if self.rev:
            try:
                return db.get_rev(self.id) == self.rev
            except ResourceNotFound:
                # this doc has been deleted.  clearly an old rev
                return False
        # we don't know if we don't know the rev
        # what's the appropriate failure mode? 
        # I think treating things like they are current is appropraite 
        # e.g. "you might want to act on this"
        return True

