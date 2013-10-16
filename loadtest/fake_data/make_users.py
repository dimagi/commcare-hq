"""
Makes fake users.

Usage:

make_web_users(domain, n)
    Makes n randomized web users. "Added" over the last 60 days

make_cc_users(domain, n)
    makes n randomized commcare users.

WebUser
    def create(cls, domain, username, password, email=None, uuid='', date='', **kwargs):

CommCareUser:
    def create(cls, domain, username, password, email=None, uuid='', date='', phone_number=None, **kwargs):
"""
import datetime, random

from corehq.apps.users.models import CommCareUser, WebUser
from corehq.apps.domain.shortcuts import create_user

from .names import names

def make_user(creator, domain, number):
    today = datetime.date.today()
    first = random.choice(names)[0]
    last = random.choice(names)[2]
    username = "{0}{1}{2}".format(first, last, number)
    email = "{0}@{1}.commcarehq.org".format(username, domain)
    created = today - datetime.timedelta(days=random.randint(0, 60))
    return creator(domain, username, 'root', email=email, date=created,
        first_name=first, last_name=last)


def make_web_user(domain, number=''):
    return make_user(WebUser.create, domain, number)


def make_cc_user(domain, number=''):
    return make_user(CommCareUser.create, domain, number)


# Below this point is for multiple users at once

def make_users(creator, domain, n, verbosity=None):
    today = datetime.date.today()
    if verbosity is None:
        verbosity = n/20 or 1
    for i in range(n):
        if i%verbosity == 0:
            print "{0}/{1} users created".format(i, n)
        first = random.choice(names)[0]
        last = random.choice(names)[2]
        username = "{0}{1}{2}".format(first, last, i)
        email = "{0}@{1}.commcarehq.org".format(username, domain)
        created = today - datetime.timedelta(days=random.randint(0, 60))
        creator(domain, username, 'root', email=email, date=created,
            first_name=first, last_name=last)

def make_web_users(domain, n):
    make_users(WebUser.create, domain, n, n/20)
    print "Successfully made %s web users" % n

def make_cc_users(domain, n, verbosity=None):
    make_users(CommCareUser.create, domain, n, n/100)
    print "Successfully made %s CommCare users" % n
