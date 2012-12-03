from couchdbkit.exceptions import ResourceConflict
from django.test import TestCase
import json
from corehq.apps.users import old_couch_user_models
from corehq.apps.users.models import CouchUser
from dimagi.utils.couch.database import get_db

COMMCARE_USER = json.loads("""{
   "_id": "COMMCARE-USER-ID",
   "status": null,
   "web_account": {
       "doc_type": "WebAccount",
       "domain_memberships": [
       ],
       "login_id": null
   },
   "first_name": null,
   "last_name": null,
   "commcare_accounts": [
       {
           "doc_type": "CommCareAccount",
           "domain": "test_domain",
           "registering_device_id": "Generated from HQ",
           "user_data": {
           },
           "login_id": "COMMCARE-USER-LOGIN-DOC-ID"
       }
   ],
   "doc_type": "CouchUser",
   "created_on": null,
   "phone_numbers": [
   ],
   "device_ids": [
       "Generated from HQ"
   ],
   "email": null
}""")

COMMCARE_USER_LOGIN_DOC = json.loads("""{
   "_id": "COMMCARE-USER-LOGIN-DOC-ID",
   "user": 206,
   "django_type": "users.hquserprofile",
   "id": 206,
   "django_user": {
       "username": "danny@test.commcarehq.org",
       "first_name": "",
       "last_name": "",
       "django_type": "auth.user",
       "is_active": true,
       "email": "",
       "is_superuser": false,
       "is_staff": false,
       "last_login": "2011-05-01T00:31:34Z",
       "groups": [
       ],
       "user_permissions": [
       ],
       "password": "sha1$salt$hash",
       "id": 206,
       "date_joined": "2011-05-01T00:31:34Z"
   }
}""")

COMMCARE_USER_TARGET = json.loads("""{
    "base_doc": "CouchUser",
    "doc_type": "CommCareUser",
    "_id": "COMMCARE-USER-LOGIN-DOC-ID",
    "domain": "test-domain",
    "username": "danny@test.commcarehq.org",
    "password": "sha1$salt$hash",
    "first_name": "",
    "last_name": "",
    "is_active": true,
    "status": null,
    "email": "",
    "user_data": {},
    "created_on": null,
    "is_staff": false,
    "phone_numbers": [],
    "date_joined": "2011-05-01T00:31:34Z",
    "is_superuser": false,
    "last_login": "2011-05-01T00:31:34Z",
    "registering_device_id": "Generated from HQ",
    "device_ids": ["Generated from HQ"]
}""")

WEB_USER = json.loads("""{
   "_id": "WEB-USER-ID",
   "status": null,
   "doc_type": "CouchUser",
   "first_name": "Alex",
   "last_name": "Roberts",
   "commcare_accounts": [
   ],
   "web_account": {
       "doc_type": "WebAccount",
       "domain_memberships": [
           {
               "doc_type": "DomainMembership",
               "domain": "test_domain",
               "last_login": null,
               "is_admin": true,
               "permissions": [
               ],
               "timezone": "UTC",
               "date_joined": null
           }
       ],
       "login_id": "WEB-USER-LOGIN-DOC-ID"
   },
   "created_on": null,
   "phone_numbers": [
   ],
   "device_ids": [
   ],
   "email": "aroberts@dimagi.com"
}""")

WEB_USER_LOGIN_DOC = json.loads("""{
   "_id": "WEB-USER-LOGIN-DOC-ID",
   "user": 246,
   "django_type": "users.hquserprofile",
   "id": 246,
   "django_user": {
       "username": "aroberts@dimagi.com",
       "first_name": "Alex",
       "last_name": "Roberts",
       "django_type": "auth.user",
       "is_active": true,
       "email": "aroberts@dimagi.com",
       "is_superuser": false,
       "is_staff": false,
       "last_login": "2011-05-26T05:09:04Z",
       "groups": [
       ],
       "user_permissions": [
       ],
       "password": "sha1$salt$hash",
       "id": 246,
       "date_joined": "2011-05-18T20:02:33Z"
   }
}""")

WEB_USER_TARGET = json.loads("""{
    "base_doc": "CouchUser",
    "doc_type": "WebUser",
    "_id": "WEB-USER-LOGIN-DOC-ID",
    "domains": ["test-domain"],
    "username": "aroberts@dimagi.com",
    "first_name": "Alex",
    "last_name": "Roberts",
    "is_active": true,
    "email": "aroberts@dimagi.com",
    "is_superuser": false,
    "is_staff": false,
    "last_login": "2011-05-26T05:09:04Z",
    "password": "sha1$salt$hash",
    "date_joined": "2011-05-18T20:02:33Z",
    "created_on": null,
    "domain_memberships": [
        {
           "doc_type": "DomainMembership",
           "domain": "test-domain",
           "last_login": null,
           "is_admin": true,
           "permissions": [
           ],
           "timezone": "UTC",
           "date_joined": null
        }
    ],
    "status": null,
    "device_ids": [],
    "phone_numbers": [],
}""")


class MigrateUsersTest(TestCase):

    def setUp(self):
        for doc in (COMMCARE_USER, COMMCARE_USER_LOGIN_DOC, WEB_USER, WEB_USER_LOGIN_DOC):
            try:
                get_db().save_doc(doc)
            except ResourceConflict:
                pass

    def test_commcare_user_migration(self):
        old_couch_user = old_couch_user_models.CouchUser.get(COMMCARE_USER['_id'])
        commcare_user = CouchUser.from_old_couch_user(old_couch_user)
        commcare_user.save(force_update=True)

        django_user = commcare_user.get_django_user()
        self.assertEqual(django_user.username, commcare_user.username)

        output = commcare_user.to_json()
        del output['_rev']
        self.assertEqual(
            json.dumps(output, sort_keys=True),
            json.dumps(COMMCARE_USER_TARGET, sort_keys=True)
        )
    def test_web_user_migration(self):
        old_couch_user = old_couch_user_models.CouchUser.get(WEB_USER['_id'])
        web_user = CouchUser.from_old_couch_user(old_couch_user)
        web_user.save(force_update=True)

        django_user = web_user.get_django_user()
        self.assertEqual(django_user.username, web_user.username)

        output = web_user.to_json()
        del output['_rev']
        self.assertEqual(
            json.dumps(output, sort_keys=True),
            json.dumps(WEB_USER_TARGET, sort_keys=True)
        )