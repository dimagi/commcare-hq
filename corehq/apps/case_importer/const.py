from __future__ import absolute_import
from __future__ import unicode_literals
from django.utils.translation import ugettext_noop
from six.moves import range


# Each column results in 3 form fields so this must be true:
#   num_columns * 3 < DATA_UPLOAD_MAX_NUMBER_FIELDS
#
# DATA_UPLOAD_MAX_NUMBER_FIELDS defaults to 1000 but there are
# a few other fields as well. Also 300 is a nice round number.
MAX_CASE_IMPORTER_COLUMNS = 300


class LookupErrors(object):
    NotFound, MultipleResults = list(range(2))


class ImportErrors(object):
    InvalidOwnerName = ugettext_noop('Invalid Owner Name')
    InvalidOwnerId = ugettext_noop('Invalid Owner ID')
    InvalidParentId = ugettext_noop('Invalid Parent ID')
    InvalidDate = ugettext_noop('Invalid Date')
    BlankExternalId = ugettext_noop('Blank External ID')
    CaseGeneration = ugettext_noop('Case Generation Error')
    DuplicateLocationName = ugettext_noop('Duplicated Location Name')
    InvalidInteger = ugettext_noop('Invalid Integer')
    ImportErrorMessage = ugettext_noop('Import Error')
