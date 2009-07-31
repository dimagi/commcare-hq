import unittest
import os
from django.contrib.auth.models import Group, User
from hq.models import *
from django.contrib.contenttypes.models import ContentType
from django.core import serializers


import hq.utils as utils

class BasicTestCase(unittest.TestCase):
    def setup(selfs):
        #EdgeType.objects.all().delete()
        #User.objects.all().delete()
        #Edge.objects.all().delete()
        pass

    def testGetAllMembers(self):
        orgs = Organization.objects.all()
        for org in orgs:
            print utils.get_members_and_supervisors(org)