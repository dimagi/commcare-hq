from dimagi.utils.mixins import UnicodeMixIn

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