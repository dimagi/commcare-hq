from django import template

register = template.Library()

@register.filter
def is_admin(couch_user, domain):
    return couch_user.is_domain_admin(domain)

@register.filter
def can_edit_users(couch_user, domain):
    return couch_user.can_edit_users(domain)

@register.filter
def can_edit_apps(couch_user, domain):
    return couch_user.can_edit_apps(domain)