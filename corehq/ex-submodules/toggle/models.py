from dimagi.ext.couchdbkit import Document


# Skeleton to avoid pickling errors due to caching that happened
# before this class moved to corehq.apps.toggle_ui.models.
class Toggle(Document):
    pass
