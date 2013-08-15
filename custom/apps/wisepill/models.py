from couchdbkit.ext.django.schema import *

class WisePillDeviceEvent(Document):
    """
    One DeviceEvent is created each time a device sends data that is 
    forwarded to the CommCareHQ WisePill API (/wisepill/device/).
    """
    domain = StringProperty()
    data = StringProperty()
    received_on = DateTimeProperty()
    case_id = StringProperty() # Document _id of the case representing the device that sent this data in
    processed = BooleanProperty()

