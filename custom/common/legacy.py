
class XFormInstanceWasRemoved:
    """Non-functional placeholder for fluff indicators

    Temporary workaround to allow removing XFormInstance while approval
    for removing custom fluff reports is pending. Fluff is no longer
    processing forms since all forms and cases have been migrated to SQL.
    """
    _doc_type = "XFormInstance"

    def to_json(self):
        return {"doc_type": self._doc_type}
