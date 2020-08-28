from django.conf import settings


DATE_FORMATS_ARR = ["yyyy-MM-dd",
                   "yyyy-MM-dd'T'HH:mm:ssZZ",
                   "yyyy-MM-dd'T'HH:mm:ss.SSSSSS",
                   "yyyy-MM-dd'T'HH:mm:ss.SSSSSS'Z'",
                   "yyyy-MM-dd'T'HH:mm:ss'Z'",
                   "yyyy-MM-dd'T'HH:mm:ssZ",
                   "yyyy-MM-dd'T'HH:mm:ssZZ'Z'",
                   "yyyy-MM-dd'T'HH:mm:ss.SSSZZ",
                   "yyyy-MM-dd'T'HH:mm:ss",
                   "yyyy-MM-dd' 'HH:mm:ss",
                   "yyyy-MM-dd' 'HH:mm:ss.SSSSSS",
                   "mm/dd/yy' 'HH:mm:ss",
]

if settings.ELASTICSEARCH_MAJOR_VERSION == 7:
    DATE_FORMATS_ARR = DATE_FORMATS_ARR + [
        # e.g. 2014-01-12T13:50:40.314+01
        "yyyy-MM-dd'T'HH:mm:ss.SSSx",
        # e.g. 2013-11-05T17:39:01+00:00Z
        "yyyy-MM-dd'T'HH:mm:ssXXX'Z'",
        # e.g. 2014-01-19T12:01:59.596+05:30
        "yyyy-MM-dd'T'HH:mm:ss.SSSXXX",
    ]

#https://github.com/elasticsearch/elasticsearch/issues/2132
#elasticsearch Illegal pattern component: t
#no builtin types for || joins
DATE_FORMATS_STRING = '||'.join(DATE_FORMATS_ARR)
