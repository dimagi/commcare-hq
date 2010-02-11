from django.contrib import admin
#from django.contrib.contenttypes import generic
from domain.models import Domain, Membership, RegistrationRequest, Settings

# GenericTabularInline works exactly backwards - it binds the generic info to the domain displayed,
# and lets us select the domain FK. "Regular" TabularInline binds the displayed domain to the FK
# and has us fill out the generic info, but doesn't display anything helpful in picking the member_id.
#
# http://opensource.washingtontimes.com/blog/post/coordt/2009/01/generic-collections-django/ has some
# good code to fix this problem.

#class MembershipInline(generic.GenericTabularInline):
class MembershipInline(admin.TabularInline):
    model = Membership
    #ct_field = 'member_type'
    #ct_fk_field = 'member_id'

class DomainAdmin(admin.ModelAdmin):
    model = Domain
    inlines = [
        MembershipInline,
    ]    

class RegistrationRequestAdmin(admin.ModelAdmin):
    model = RegistrationRequest
    
class SettingsAdmin(admin.ModelAdmin):
    model = Settings

admin.site.register(Domain, DomainAdmin)    
admin.site.register(RegistrationRequest, RegistrationRequestAdmin)
admin.site.register(Settings, SettingsAdmin)
