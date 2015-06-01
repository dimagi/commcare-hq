
class DeviceLogMigrationPillow(object):
    document_class = XFormInstance
    couch_filter = 'couchforms/devicelogs'
    is_deleted = lambda doc:, doc
    get_db = lambda: DeviceLogXFormInstance.get_db()

    def change_transport(self, doc):

        if self.is_deleted(doc):
            self.get_db().save(doc)

