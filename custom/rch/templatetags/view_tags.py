from django import template

register = template.Library()


@register.filter
def mask_aadhar_number(aadhar_number):
    return 'X' * 8 + aadhar_number[-4:]
