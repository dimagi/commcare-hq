from collections import namedtuple

ExportLoggingContext = namedtuple('ExportLoggingContext', [
    'download_id',
    'username',
    'trigger',
])
