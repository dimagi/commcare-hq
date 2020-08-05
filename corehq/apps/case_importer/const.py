from django.utils.translation import ugettext_noop

# Each column results in 3 form fields so this must be true:
#   num_columns * 3 < DATA_UPLOAD_MAX_NUMBER_FIELDS
#
# DATA_UPLOAD_MAX_NUMBER_FIELDS defaults to 5000 but there are
# a few other fields as well. Also 1600 is a nice round number.
MAX_CASE_IMPORTER_COLUMNS = 1600


class LookupErrors(object):
    NotFound, MultipleResults = list(range(2))
