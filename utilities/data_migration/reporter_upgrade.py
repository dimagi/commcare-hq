None
#!/usr/bin/env python
# -*- coding: utf-8 -*-

import datetime
import os
from django.utils import simplejson


def run():
    print "starting"
    from hq.models import ExtUser, ReporterProfile
    from reporters.models import Reporter, PersistantBackend, PersistantConnection
    
    all_users = ExtUser.objects.all()
    for user in all_users:
        print "processing user %s" % user
        rep = user.reporter
        if rep:
            print "%s already has attached reporter object!  %s" % (user, reporter)
        else:
            rep = Reporter()
            # if they have a first and last name set, use those, 
            # otherwise just use the login
            if user.first_name and user.last_name:
                
                alias, fn, ln = Reporter.parse_name("%s %s" % (user.first_name, user.last_name))
            else:
                alias, fn, ln = Reporter.parse_name(user.username)
            print "Chose alias: %s first last: %s %s" % (alias, fn, ln) 
            rep.first_name = fn
            rep.last_name = ln
            rep.alias = alias
            rep.save()
        
        profile = ReporterProfile()
        profile.reporter = rep
        profile.chw_id = user.chw_id
        profile.chw_username = user.chw_username
        profile.domain = user.domain 
        profile.save()
        print "Saved profile %s for %s" % (profile, user)
        if user.primary_phone:
            # create a backend / connection for them.  This is 
            # still a little hazy as it's not clear how the 
            # backend is properly chosen
            
            # this will create an arbitrary backend if none is 
            # found 
            if len(PersistantBackend.objects.all()) == 0:
                PersistantBackend.objects.create(slug="data_migration", 
                                                 title="Data Migration Backend")
            backend = PersistantBackend.objects.all()[0]
            try:
                conn = PersistantConnection.objects.create(backend=backend, 
                                                           identity=user.primary_phone, 
                                                           reporter=rep)
                print "created connection %s for %s" % (conn, user)
            except Exception, e:
                print "Error creating connection for %s for number %s.  Is it possible you have duplicate phone numbers?" % (user, user.primary_phone)
    print "done"
                 
        
            
            
        
            
    
            
