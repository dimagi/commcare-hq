

from __future__ import unicode_literals
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

#https://github.com/elasticsearch/elasticsearch/issues/2132
#elasticsearch Illegal pattern component: t
#no builtin types for || joins
DATE_FORMATS_STRING = '||'.join(DATE_FORMATS_ARR)
