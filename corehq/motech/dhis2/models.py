import bz2
from base64 import b64decode, b64encode

from django.core.exceptions import ValidationError
from django.db import models

from dimagi.ext.couchdbkit import (
    Document,
    DocumentSchema,
    IntegerProperty,
    SchemaListProperty,
    StringProperty,
)

from corehq.motech.dhis2.const import (
    SEND_FREQUENCIES,
    SEND_FREQUENCY_MONTHLY,
)
from corehq.motech.models import ConnectionSettings


# UNUSED
class Dhis2Connection(models.Model):
    domain = models.CharField(max_length=255, unique=True)
    server_url = models.CharField(max_length=255, null=True)
    username = models.CharField(max_length=255)
    password = models.CharField(max_length=255, null=True)
    skip_cert_verify = models.BooleanField(default=False)

    @property
    def plaintext_password(self):
        plaintext_bytes = bz2.decompress(b64decode(self.password))
        return plaintext_bytes.decode('utf8')

    @plaintext_password.setter
    def plaintext_password(self, plaintext):
        # Use simple symmetric encryption. We don't need it to be
        # strong, considering we'd have to store the algorithm and the
        # key together anyway; it just shouldn't be plaintext.
        # (2020-03-09) Not true. The key is stored separately.
        plaintext_bytes = plaintext.encode('utf8')
        self.password = b64encode(bz2.compress(plaintext_bytes))

    def save(self, *args, **kwargs):
        raise ValidationError(
            'Dhis2Connection is unused. Use ConnectionSettings instead.'
        )


class DataValueMap(DocumentSchema):
    column = StringProperty(required=True)
    data_element_id = StringProperty(required=True)
    category_option_combo_id = StringProperty(required=True)
    comment = StringProperty()


class DataSetMap(Document):
    # domain and UCR uniquely identify a DataSetMap
    domain = StringProperty()
    connection_settings_id = IntegerProperty(required=False, default=None)
    ucr_id = StringProperty()  # UCR ReportConfig id

    description = StringProperty()
    frequency = StringProperty(choices=SEND_FREQUENCIES, default=SEND_FREQUENCY_MONTHLY)
    # Day of the month for monthly/quarterly frequency. Day of the week
    # for weekly frequency. Uses ISO-8601, where Monday = 1, Sunday = 7.
    day_to_send = IntegerProperty()
    data_set_id = StringProperty()  # If UCR adds values to an existing DataSet
    org_unit_id = StringProperty()  # If all values are for the same OrganisationUnit.
    org_unit_column = StringProperty()  # if not org_unit_id: use org_unit_column
    period = StringProperty()  # If all values are for the same period. Monthly is YYYYMM, quarterly is YYYYQ#
    period_column = StringProperty()  # if not period: use period_column

    attribute_option_combo_id = StringProperty()  # Optional. DHIS2 defaults this to categoryOptionCombo
    complete_date = StringProperty()  # Optional

    datavalue_maps = SchemaListProperty(DataValueMap)

    @property
    def connection_settings(self):
        if self.connection_settings_id:
            return ConnectionSettings.objects.get(pk=self.connection_settings_id)
