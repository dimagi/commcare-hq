from __future__ import absolute_import
import math
import uuid
from crispy_forms import layout as crispy
from django import forms
from django.core.validators import RegexValidator
from django.utils.translation import ugettext as _
from dimagi.utils.decorators.memoized import memoized
from corehq import toggles
from corehq.apps.custom_data_fields import CustomDataEditor
from corehq.apps.locations.forms import LocationFormSet, LocationForm
from corehq.apps.locations.models import LocationType
from corehq.apps.users.forms import clean_mobile_worker_username
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.signals import commcare_user_post_save
from .const import (
    AGENCY_LOCATION_FIELDS,
    AGENCY_LOCATION_TYPES,
    AGENCY_USER_FIELDS,
    DEFAULT_MOBILE_WORKER_ROLE,
    PRIVATE_SECTOR_WORKER_ROLE,
)
from .models import AgencyIdCounter, IssuerId


def save_user_callback(sender, couch_user, **kwargs):
    commcare_user = couch_user  # django signals enforce param names
    if toggles.ENIKSHAY.enabled(commcare_user.domain):
        changed = False
        if kwargs.get('is_new_user', False):
            changed = set_default_role(commcare_user.domain, commcare_user) or changed
        changed = set_issuer_id(commcare_user.domain, commcare_user) or changed
        changed = add_drtb_hiv_to_dto(commcare_user.domain, commcare_user) or changed
        if changed:
            commcare_user.save(fire_signals=False)


def set_default_role(domain, commcare_user):
    from corehq.apps.users.models import UserRole
    if commcare_user.get_role(domain):
        return
    roles = UserRole.by_domain_and_name(domain, DEFAULT_MOBILE_WORKER_ROLE)
    if roles:
        commcare_user.set_role(domain, roles[0].get_qualified_id())
        commcare_user.save()


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


def set_enikshay_device_id(user, device_id):
    # device_id was JUST set, so it must be in there
    device_number = [device.device_id for device in user.devices].index(device_id) + 1
    if user.user_data.get('id_device_number') != device_number:
        user.user_data['id_device_number'] = device_number
        user.user_data['id_device_body'] = compress_nikshay_id(device_number, 0)
        return True
    return False


def set_issuer_id(domain, user):
    """Add a serially increasing custom user data "Issuer ID" to the user, as
    well as a human-readable compressed form."""
    changed = False
    if not user.user_data.get('id_issuer_number', None):
        issuer_id, created = IssuerId.objects.get_or_create(domain=domain, user_id=user._id)
        user.user_data['id_issuer_number'] = issuer_id.pk
        user.user_data['id_issuer_body'] = compress_nikshay_id(issuer_id.pk, 3)
        changed = True

    return changed


def add_drtb_hiv_to_dto(domain, user):
    location = user.get_sql_location(domain)
    if location and location.location_type.code == 'drtb-hiv':
        # also assign user to the parent DTO
        loc_ids = user.get_location_ids(domain)
        if location.parent.location_id not in loc_ids:
            user.add_to_assigned_locations(location.parent, commit=False)
            return True


def connect_signals():
    commcare_user_post_save.connect(save_user_callback, dispatch_uid="save_user_callback")


def _make_fields_type_specific(domain, form, fields_to_loc_types):
    """Make certain fields only appear for specified loctypes"""
    fs = form.helper.layout[0]
    assert isinstance(fs, crispy.Fieldset)
    codes_to_names = dict(LocationType.objects
                          .filter(domain=domain)
                          .values_list('code', 'name'))
    for i, field in enumerate(fs.fields):
        if field in fields_to_loc_types:
            loc_type_name = codes_to_names[fields_to_loc_types[field]]
            # loc_type() is available because this is inside the location form
            fs[i] = crispy.Div(
                field,
                data_bind="visible: loc_type() === '{}'".format(loc_type_name)
            )
    return form


class ENikshayLocationUserDataEditor(CustomDataEditor):
    """Custom User Data on Virtual Location User (agency) creation"""

    @property
    @memoized
    def fields(self):
        # non-required fields are typically excluded from creation UIs
        fields_to_include = [field[0] for field in AGENCY_USER_FIELDS]
        return [
            field for field in self.model.get_fields(required_only=False)
            if field.is_required or field.slug in fields_to_include
        ]

    def init_form(self, post_dict=None):
        form = super(ENikshayLocationUserDataEditor, self).init_form(post_dict)
        fields_to_loc_types = {
            'pcp_professional_org_membership': 'pcp',
            'pac_qualification': 'pac',
            'pcp_qualification': 'pcp',
            'plc_lab_collection_center_name': 'plc',
            'plc_lab_or_collection_center': 'plc',
            'plc_accredidation': 'plc',
            'plc_tb_tests': 'plc',
            'pcc_pharmacy_name': 'pcc',
            'pcc_pharmacy_affiliation': 'pcc',
            'pcc_tb_drugs_in_stock': 'pcc',
        }
        return _make_fields_type_specific(self.domain, form, fields_to_loc_types)

    def _make_field(self, field):
        if field.slug == 'language_code':
            return forms.ChoiceField(
                label=field.label,
                required=True,
                choices=[
                    ('', _('Select one')),
                    ("en", "English"),
                    ("hin", "Hindi"),
                    ("mar", "Marathi"),
                    ("bho", "Bhojpuri"),
                    ('guj', "Gujarati"),
                ],
            )
        if field.slug == 'contact_phone_number':
            regexp = "^91[0-9]{10}$"
            help_text = "Please enter only digits. Enter 91 followed by the 10-digit national number."
            return forms.CharField(
                widget=forms.TextInput(attrs={"pattern": regexp, "title": help_text}),
                label=field.label,
                required=True,
                validators=[RegexValidator(regexp, help_text)],
            )
        if field.slug == 'user_level':
            return forms.ChoiceField(
                label=field.label,
                required=field.is_required,
                choices=[
                    ("real", "Real"),
                    ("dev", "Developer"),
                    ("test", "Test"),
                ],
            )
        return super(ENikshayLocationUserDataEditor, self)._make_field(field)


class ENikshayUserLocationDataEditor(CustomDataEditor):
    """Custom Location Data on Virtual Location User (agency) creation"""

    @property
    @memoized
    def fields(self):
        if not self.required_only:
            return self.model.get_fields(required_only=False)

        # non-required fields are typically excluded from creation UIs
        fields_to_include = [field[0] for field in AGENCY_LOCATION_FIELDS]
        return [
            field for field in self.model.get_fields(required_only=False)
            if field.is_required or field.slug in fields_to_include
        ]

    def init_form(self, post_dict=None):
        form = super(ENikshayUserLocationDataEditor, self).init_form(post_dict)
        fields_to_loc_types = {
            'facility_type': 'pcp',
            'plc_hf_if_nikshay': 'plc',
        }
        return _make_fields_type_specific(self.domain, form, fields_to_loc_types)

    def _make_field(self, field):
        if field.slug == 'private_sector_org_id':
            return forms.ChoiceField(
                label=field.label,
                required=field.is_required,
                choices=[
                    ('', _('Select one')),
                    ('1', "PATH"),
                    ('2', "MJK"),
                    ('3', "Alert-India"),
                    ('4', "WHP-Patna"),
                    ('5', "DTO-Mehsana"),
                    ('6', "Vertex"),
                    ('7', "Accenture"),
                    ('8', "BMGF"),
                    ('9', "EY"),
                    ('10', "CTD"),
                    ('11', "Nagpur"),
                    ('12', "Nagpur-rural"),
                    ('13', "Nagpur_Corp"),
                    ('14', "Surat"),
                    ('15', "SMC"),
                    ('16', "Surat_Rural"),
                    ('17', "Rajkot"),
                    ('18', "WHP-AMC"),
                ],
            )
        return super(ENikshayUserLocationDataEditor, self)._make_field(field)


class ENikshayLocationForm(LocationForm):

    def save(self, metadata):
        location = super(ENikshayLocationForm, self).save(metadata)
        if location.location_type.code in ['pcp', 'pac', 'plc', 'pcc']:
            if not location.metadata.get('private_sector_agency_id'):
                private_sector_agency_id = str(AgencyIdCounter.get_new_agency_id())
                location.metadata['private_sector_agency_id'] = private_sector_agency_id
                location.name = '%s - %s' % (location.name, private_sector_agency_id)
                location.save()
        return location


def get_new_username_and_id(domain, attempts_remaining=3):
    if attempts_remaining <= 0:
        raise AssertionError(
            "3 IssuerIds were created, but they all corresponded to existing "
            "users.  Are there a bunch of users with usernames matching "
            "possible compressed ids?  Better investigate.")

    user_id = uuid.uuid4().hex
    issuer_id, created = IssuerId.objects.get_or_create(domain=domain, user_id=user_id)
    compressed_issuer_id = compress_nikshay_id(issuer_id.pk, 3)
    try:
        return clean_mobile_worker_username(domain, compressed_issuer_id), user_id
    except forms.ValidationError:
        issuer_id.delete()
        return get_new_username_and_id(domain, attempts_remaining - 1)


class ENikshayLocationFormSet(LocationFormSet):
    """Location, custom data, and possibly location user and data forms"""
    _location_form_class = ENikshayLocationForm
    _location_data_editor = ENikshayUserLocationDataEditor
    _user_data_editor = ENikshayLocationUserDataEditor

    @property
    @memoized
    def user(self):
        user_data = (self.custom_user_data.get_data_to_save()
                     if self.custom_user_data.is_valid() else {})
        password = self.user_form.cleaned_data.get('password', "")
        first_name = self.user_form.cleaned_data.get('first_name', "")
        last_name = self.user_form.cleaned_data.get('last_name', "")

        username, user_id = get_new_username_and_id(self.domain)

        return CommCareUser.create(
            self.domain,
            username=username,  # TODO should this be compressed?
            password=password,
            device_id="Generated from HQ",
            first_name=first_name,
            last_name=last_name,
            user_data=user_data,
            uuid=user_id,
            commit=False,
        )

    def _get_user_form(self, bound_data):
        form = super(ENikshayLocationFormSet, self)._get_user_form(bound_data)
        # Hide username, since we'll set it automatically
        form.fields.pop('username')
        return form

    def save(self):
        if (self.location_form.cleaned_data['location_type_object'].code in AGENCY_LOCATION_TYPES
                and self.include_user_forms):
            self._set_user_role(self.user, PRIVATE_SECTOR_WORKER_ROLE)
        super(ENikshayLocationFormSet, self).save()

    def _set_user_role(self, user, role_name):
        from corehq.apps.users.models import UserRole
        roles = UserRole.by_domain_and_name(self.domain, role_name)
        if len(roles) == 0:
            raise AssertionError("There is no user role '{}', did someone change the name?"
                                 .format(role_name))
        elif len(roles) > 1:
            raise AssertionError("There are more than one roles called '{}', please delete or "
                                 "rename one.".format(role_name))
        else:
            role = roles[0]
            user.set_role(self.domain, role.get_qualified_id())
