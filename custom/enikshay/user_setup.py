"""
This uses signals to hook in to user and location forms for custom validation
and some autogeneration. These additions are turned on by a feature flag, but
domain and HQ admins are excepted, in case we ever need to violate the
assumptions laid out here.
"""
import math
import re
from django.utils.text import slugify
from django.utils.translation import ugettext as _
from corehq import toggles
from corehq.apps.custom_data_fields import CustomDataEditor
from corehq.apps.locations.forms import LocationFormSet, LocationForm
from corehq.apps.users.forms import NewMobileWorkerForm
from corehq.apps.users.signals import clean_commcare_user, commcare_user_post_save
from corehq.apps.locations.signals import clean_location
from .models import IssuerId

TYPES_WITH_REQUIRED_NIKSHAY_CODES = ['sto', 'dto', 'tu', 'dmc', 'phi']
LOC_TYPES_TO_USER_TYPES = {
    'phi': ['to', 'tbhv', 'mo-phi'],
    'tu': ['sts', 'stls'],
    'dmc': ['lt-dmc'],
    'cdst': ['lt-cdst'],
    'dto': ['dto', 'deo'],
    'cto': ['cto'],
    'sto': ['sto'],
    'drtb-hiv': ['drtb-hiv'],
}


def skip_custom_setup(domain, request_user):
    return not toggles.ENIKSHAY.enabled(domain) or request_user.is_domain_admin(domain)


def clean_user_callback(sender, domain, request_user, user, forms, **kwargs):
    if skip_custom_setup(domain, request_user):
        return

    new_user_form = forms.get('NewMobileWorkerForm')
    update_user_form = forms.get('UpdateCommCareUserInfoForm')
    custom_data = forms.get('CustomDataEditor')
    location_form = forms.get('CommtrackUserForm')

    if update_user_form or new_user_form:
        if not custom_data:
            raise AssertionError("Expected user form and custom data form to be submitted together")

        if sender == 'LocationFormSet':
            location_type = new_user_form.data['location_type']
        elif new_user_form:
            location_type = validate_location(domain, new_user_form).location_type.code
        else:
            location = user.get_sql_location(domain)
            if not location:
                return
            location_type = user.get_sql_location(domain).location_type.code

        if 'usertype' not in custom_data.form.cleaned_data:
            return  # There was probably a validation error
        usertype = custom_data.form.cleaned_data['usertype']
        validate_usertype(location_type, usertype, custom_data)
        if new_user_form:
            set_user_role(domain, user, usertype, new_user_form)
        else:
            validate_role_unchanged(domain, user, update_user_form)

    if location_form:
        location_form.add_error('assigned_locations', _("You cannot edit the location of existing users."))


def validate_usertype(location_type, usertype, custom_data):
    """Restrict choices for custom user data role field based on the chosen
    location's type"""
    allowable_usertypes = LOC_TYPES_TO_USER_TYPES[location_type]
    if usertype not in allowable_usertypes:
        msg = _("'User Type' must be one of the following: {}").format(', '.join(allowable_usertypes))
        custom_data.form.add_error('usertype', msg)


def set_user_role(domain, user, usertype, user_form):
    """Auto-assign mobile workers a role based on usertype"""
    from corehq.apps.users.models import UserRole
    roles = UserRole.by_domain_and_name(domain, usertype)
    if len(roles) == 0:
        msg = _("There is no role called '{}', you cannot create this user "
                "until that role is created.").format(usertype)
        user_form.add_error(None, msg)
    elif len(roles) > 1:
        msg = _("There are more than one roles called '{}', please delete or "
                "rename one.").format(usertype)
        user_form.add_error(None, msg)
    else:
        role = roles[0]
        user.set_role(domain, role.get_qualified_id())


def validate_role_unchanged(domain, user, user_form):
    """Web user role is not editable"""
    existing_role = user.get_domain_membership(domain).role
    if not existing_role:
        return
    existing_role_id = existing_role.get_qualified_id()
    specified_role_id = user_form.cleaned_data['role']
    if existing_role_id != specified_role_id:
        msg = _("You cannot modify the user's role.  It must be {}").format(existing_role.name)
        user_form.add_error('role', msg)


def validate_location(domain, user_form):
    """Force a location to be chosen"""
    from corehq.apps.locations.models import SQLLocation
    location_id = user_form.cleaned_data['location_id']
    if location_id:
        try:
            return SQLLocation.active_objects.get(
                domain=domain, location_id=location_id)
        except SQLLocation.DoesNotExist:
            pass
    user_form.add_error('location_id', _("You must select a location."))


def clean_location_callback(sender, domain, request_user, location, forms, **kwargs):
    if not toggles.ENIKSHAY.enabled(domain) or request_user.is_domain_admin(domain):
        return

    location_form = forms.get('LocationForm')
    custom_data = forms.get('CustomDataEditor')

    if location_form.is_new_location:
        validate_nikshay_code(domain, location_form, custom_data)
        set_site_code(location_form, custom_data)
    else:
        validate_nikshay_code_unchanged(location, custom_data)

    set_available_tests(location, location_form)


def get_site_code(name, nikshay_code, type_code, parent):

    def code_ify(word):
        return slugify(re.sub(r'\s+', '_', word))

    nikshay_code = code_ify(nikshay_code)
    if nikshay_code in map(str, range(0, 10)):
        nikshay_code = "0{}".format(nikshay_code)

    parent_site_code = parent.site_code
    parent_prefix = ('drtbhiv_' if parent.location_type.code == 'drtb-hiv' else
                     "{}_".format(parent.location_type.code))
    if parent_site_code.startswith(parent_prefix):
        parent_site_code = parent_site_code[len(parent_prefix):]

    name_code = code_ify(name)

    if type_code in ['sto', 'cdst']:
        return '_'.join([type_code, nikshay_code])
    elif type_code == 'cto':
        return '_'.join([type_code, parent_site_code, name_code])
    elif type_code == 'drtb-hiv':
        return '_'.join(['drtbhiv', parent_site_code])
    elif type_code in ['dto', 'tu', 'dmc', 'phi']:
        return '_'.join([type_code, parent_site_code, nikshay_code])
    elif type_code in ['ctd', 'drtb']:
        return None  # we don't do anything special for these yet
    else:
        raise AssertionError('This eNikshay location has an unrecognized type, {}'.format(type_code))


def set_site_code(location_form, custom_data):
    # https://docs.google.com/document/d/1Pr19kp5cQz9412Q1lbVgszeZJTv0XRzizb0bFHDxvoA/edit#heading=h.9v4rs82o0soc
    nikshay_code = custom_data.form.cleaned_data.get('nikshay_code') or ''
    type_code = location_form.cleaned_data['location_type']
    parent = location_form.cleaned_data['parent']
    name = location_form.cleaned_data['name']
    location_form.cleaned_data['site_code'] = get_site_code(name, nikshay_code, type_code, parent)


def validate_nikshay_code(domain, location_form, custom_data):
    """When locations are created, enforce that a custom location data field
    (Nikshay code) is unique amongst sibling locations"""
    from corehq.apps.locations.models import SQLLocation
    nikshay_code = custom_data.form.cleaned_data.get('nikshay_code', None)
    loctype = location_form.cleaned_data['location_type']
    if loctype not in TYPES_WITH_REQUIRED_NIKSHAY_CODES:
        return
    if not nikshay_code:
        location_form.add_error(None, "You cannot create this location without providing a nikshay_code.")
    parent = location_form.cleaned_data['parent']
    sibling_codes = [
        loc.metadata.get('nikshay_code', None)
        for loc in SQLLocation.objects.filter(domain=domain, parent=parent)
    ]
    if nikshay_code in sibling_codes:
        msg = "Nikshay Code '{}' is already in use.".format(nikshay_code)
        custom_data.form.add_error('nikshay_code', msg)


def validate_nikshay_code_unchanged(location, custom_data):
    """Block edit of custom location data nikshay code after creation"""
    specified_nikshay_code = custom_data.form.cleaned_data.get('nikshay_code', None)
    existing_nikshay_code = location.metadata.get('nikshay_code', None)
    if existing_nikshay_code and specified_nikshay_code != existing_nikshay_code:
        msg = "You cannot modify the Nikshay Code of an existing location."
        custom_data.form.add_error('nikshay_code', msg)


def set_available_tests(location, location_form):
    if location_form.cleaned_data['location_type'] == 'cdst':
        location.metadata['tests_available'] = 'cbnaat'


def save_user_callback(sender, couch_user, **kwargs):
    commcare_user = couch_user  # django signals enforce param names
    if toggles.ENIKSHAY.enabled(commcare_user.domain):
        set_issuer_id(commcare_user.domain, commcare_user)
        add_drtb_hiv_to_dto(commcare_user.domain, commcare_user)


def compress_nikshay_id(serial_id, body_digit_count):
    return compress_id(
        serial_id=serial_id,
        growth_symbols=list("HLJXYUWMNV"),
        lead_symbols=list("ACE3459KFPRT"),
        body_symbols=list("ACDEFHJKLMNPQRTUVWXY3479"),
        body_digit_count=body_digit_count,
    )


def compress_id(serial_id, growth_symbols, lead_symbols, body_symbols, body_digit_count):
    """Accepts an integer ID and compresses it according to the spec here:
    https://docs.google.com/document/d/11Nxk3XMuae9S4L3JZc4FCVTocLz6bOC-glclrgxnQ5o/"""
    if not growth_symbols or not lead_symbols:
        raise AssertionError("We need both growth and lead symbols")

    if set(growth_symbols) & set(lead_symbols):
        raise AssertionError("You cannot use the same symbol as both a growth and a lead")

    lead_digit_base = len(lead_symbols)
    growth_digit_base = len(growth_symbols)
    body_digit_base = len(body_symbols)
    max_fixed_length_size = (body_digit_base ** body_digit_count) * lead_digit_base

    if serial_id >= max_fixed_length_size:
        times_over_max = serial_id / max_fixed_length_size
        growth_digit_count = int(math.log(times_over_max, growth_digit_base)) + 1
    else:
        growth_digit_count = 0

    digit_bases = ([growth_digit_base] * growth_digit_count
                   + [lead_digit_base]
                   + [body_digit_base] * body_digit_count)

    divisors = [1]
    for digit_base in reversed(digit_bases[1:]):
        divisors.insert(0, divisors[0] * digit_base)

    remainder = serial_id
    counts = []
    for divisor in divisors:
        counts.append(remainder / divisor)
        remainder = remainder % divisor

    if remainder != 0:
        raise AssertionError("Failure while encoding ID {}!".format(serial_id))

    output = []
    for i, count in enumerate(counts):
        if i < growth_digit_count:
            output.append(growth_symbols[count])
        elif i == growth_digit_count:
            output.append(lead_symbols[count])
        else:
            output.append(body_symbols[count])
    return ''.join(output)


def get_last_used_device_number(user):
    if not user.devices:
        return None
    _, index = max((device.last_used, i) for i, device in enumerate(user.devices))
    return index + 1


def set_issuer_id(domain, user):
    """Add a serially increasing custom user data "Issuer ID" to the user, as
    well as a human-readable compressed form."""
    changed = False
    if not user.user_data.get('id_issuer_number', None):
        issuer_id, created = IssuerId.objects.get_or_create(domain=domain, user_id=user._id)
        user.user_data['id_issuer_number'] = issuer_id.pk
        user.user_data['id_issuer_body'] = compress_nikshay_id(issuer_id.pk, 3)
        changed = True

    device_number = get_last_used_device_number(user)
    if device_number and user.user_data.get('id_device_number', None) != device_number:
        user.user_data['id_device_number'] = device_number
        user.user_data['id_device_body'] = compress_nikshay_id(device_number, 0)
        changed = True

    if changed:
        # note that this is saving the user a second time 'cause it needs a
        # user id first, but if refactoring, be wary of a loop!
        user.save()


def add_drtb_hiv_to_dto(domain, user):
    location = user.get_sql_location(domain)
    if location and location.location_type.code == 'drtb-hiv':
        # also assign user to the parent DTO
        loc_ids = user.get_location_ids(domain)
        if location.parent.location_id not in loc_ids:
            user.add_to_assigned_locations(location.parent)


def connect_signals():
    clean_location.connect(clean_location_callback, dispatch_uid="clean_location_callback")
    clean_commcare_user.connect(clean_user_callback, dispatch_uid="clean_user_callback")
    commcare_user_post_save.connect(save_user_callback, dispatch_uid="save_user_callback")


class ENikshayNewMobileWorkerForm(NewMobileWorkerForm):
    """Mobile worker list view create modal"""
    def __init__(self, *args, **kwargs):
        super(ENikshayNewMobileWorkerForm, self).__init__(*args, **kwargs)


class ENikshayUserDataEditor(CustomDataEditor):
    """Custom User Data (everywhere it turns up)"""
    def __init__(self, *args, **kwargs):
        super(ENikshayUserDataEditor, self).__init__(*args, **kwargs)


class ENikshayLocationFormSet(LocationFormSet):
    """Location, custom data, and possibly location user and data forms"""
    user_form_class = ENikshayNewMobileWorkerForm

    def __init__(self, *args, **kwargs):
        print 'ENikshayLocationFormSet'
        super(ENikshayLocationFormSet, self).__init__(*args, **kwargs)
