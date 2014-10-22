import functools
from corehq.ext.datetime import UTCDateTime
from corehq.ext.unittest import Corpus

UTCDateTimeExactCorpus = functools.partial(
    Corpus, override_equals={UTCDateTime: UTCDateTime.exact_equals})
