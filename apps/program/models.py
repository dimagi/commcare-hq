#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4

from django.db import models
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic



from domain.models import Domain

class Program(models.Model):
    """
    A program is a subset of a domain - typically a logical grouping 
    of stuff within a domain.
    """
    
    name = models.CharField(max_length=100, help_text="Name of Program")
    domain = models.ForeignKey(Domain)
    
    def __unicode__(self):
        return self.name
    
    def get_users(self):
        """Convenience accessor for the users in a program"""
        return User.objects.filter(program_membership__program = self)
    
    def add_user(self, user, is_active=True):
        """
        Convenience method to add a user to a program, returning 
        the created membership object.
        """
        ct = ContentType.objects.get_for_model(User)
        mem = ProgramMembership()
        mem.program = self
        mem.program_member_type = ct
        mem.program_member_id = user.id
        mem.is_active = is_active
        mem.save()
        return mem        
    
    def remove_user(self, user):
        """
        Convenience method to remove a user from a program.
        """
        ct = ContentType.objects.get_for_model(User)
        membership = ProgramMembership.objects.get(program = self,
                                                   program_member_type = ct,
                                                   program_member_id = user.id)
        membership.delete()
        
member_limits = {'model__in':('user')}
                                         
class ProgramMembership(models.Model):
    # this very much mirrors domain membership, for clarity
    
    program = models.ForeignKey(Program)
    program_member_type = models.ForeignKey(ContentType, limit_choices_to=member_limits)
    program_member_id = models.PositiveIntegerField()
    program_member_object = generic.GenericForeignKey('member_type', 'member_id')
    is_active = models.BooleanField(default=False)

    def __unicode__(self):
        return str(self.member_type) + str(self.member_id) + str(self.member_object)

# monkey-patch users.  See domain/models.py for details
if not hasattr(User, "program_membership"):
    User.add_to_class('program_membership', 
                      generic.GenericRelation( ProgramMembership, content_type_field='program_member_type', 
                                               object_id_field='program_member_id' ) )

