from __future__ import absolute_import
from __future__ import unicode_literals
import json

commcare_build_config  = json.loads("""{
   "_id": "config--commcare-builds",
   "doc_type": "CommCareBuildConfig",
   "preview": {
       "version": "1.2.1",
       "build_number": null,
       "latest": true
   },
   "defaults": [{
       "version": "1.2.1",
       "build_number": null,
       "latest": true
   }, {
       "version": "2.0.0",
       "build_number": null,
       "latest": true
   }],
   "application_versions": ["1.0", "2.0"],
   "menu": [
       {
           "build": {
               "version": "1.1.1",
               "build_number": null,
               "latest": true
           },
           "label": "CommCare 1.1.1"
       },
       {
           "build": {
               "version": "1.2.1",
               "build_number": null,
               "latest": true
           },
           "label": "CommCare 1.2.1"
       },
       {
           "build": {
               "version": "1.3.0",
               "build_number": null,
               "latest": true
           },
           "label": "CommCare 1.3 (RC5)"
       },
       {
           "build": {
               "version": "2.0.0",
               "build_number": null,
               "latest": true
           },
           "label": "CommCare 2.0 (unstable)"
       }
   ],
   "ID": "config--commcare-builds"
}""")
