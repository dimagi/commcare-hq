from __future__ import absolute_import
from __future__ import unicode_literals
from casexml.apps.case.signals import cases_received
from casexml.apps.case.models import XFormInstance
from fluff.signals import indicator_document_updated
import json
from dimagi.utils.couch import get_redis_client, get_redis_lock, release_lock
from django.core.exceptions import ObjectDoesNotExist
from custom.m4change.constants import M4CHANGE_DOMAINS, ALL_M4CHANGE_FORMS, IMMUNIZATION_FORMS, \
    BOOKED_DELIVERY_FORMS, UNBOOKED_DELIVERY_FORMS, BOOKING_FORMS, FOLLOW_UP_FORMS, REDIS_FIXTURE_KEYS, \
    REDIS_FIXTURE_LOCK_KEYS
from custom.m4change.models import McctStatus
from six.moves import range


def _create_mcct_status_row(form_id, status, domain, received_on, registration_date, immunized, is_booking,
                            is_stillbirth):
    try:
        mcct_status = McctStatus.objects.get(form_id__exact=form_id)
        mcct_status.status = status
        mcct_status.domain = domain
        mcct_status.received_on = received_on
        mcct_status.registration_date = registration_date
        mcct_status.immunized = immunized
        mcct_status.is_booking = is_booking
        mcct_status.is_stillbirth = is_stillbirth
        mcct_status.save()
    except ObjectDoesNotExist:
        mcct_status = McctStatus(form_id=form_id, status=status, domain=domain,
                                 received_on=received_on, registration_date=registration_date,
                                 immunized=immunized, is_booking=is_booking, is_stillbirth=is_stillbirth)
        mcct_status.save()


def _get_registration_date(form, case):
    if form.xmlns in BOOKING_FORMS + UNBOOKED_DELIVERY_FORMS:
        return form.received_on.date()
    parent = case.parent
    mother_case = case if parent is None else parent
    return mother_case.booking if hasattr(mother_case, "booking") else case.opened_on.date()


def _handle_duplicate_form(xform, cases):
    for case in cases:
        forms = case.get_forms()
        for form in forms:
            if xform.xmlns == form.xmlns and xform._id != form._id and \
                            xform.received_on.date() == form.received_on.date():
                form.archive()
                return


def _filter_forms(xform, cases):
    """
        Every time a form is submitted go through the related cases' histories
        and update the statuses for all relevant records.
        Booking forms are always set to 'eligible', whereas immunization, booked-and unbooked delivery
        forms are 'eligible' only in case the 'immunization_given' field is present and not empty.
        In all other cases the last form's status is set to 'eligible', while the others are 'hidden'.
    """
    forms = []
    save_indices = []
    immunized = False
    invalid_forms = [status.form_id for status in
                     McctStatus.objects.filter(status__in=["rejected", "reviewed", "approved", "paid"])]
    for case in cases:
        forms += [(form_object, _get_registration_date(form_object, case), form_object.received_on)
                  for form_object in case.get_forms() if form_object._id not in invalid_forms]
    forms = sorted(forms, key=lambda f:f[2])
    pnc_forms = [form for form in forms if form[0].xmlns
                 in IMMUNIZATION_FORMS + BOOKED_DELIVERY_FORMS + UNBOOKED_DELIVERY_FORMS
                 if len(form[0].form.get("immunization_given", "")) > 0]
    for index in range(0, len(forms)):
        form = forms[index][0]
        registration_date = forms[index][1]
        if form.xmlns in BOOKING_FORMS:
            _create_mcct_status_row(form._id, "eligible", form.domain, form.received_on.date(),
                                    registration_date, False, True, False)
            save_indices.append(index)
        elif form.xmlns in IMMUNIZATION_FORMS + BOOKED_DELIVERY_FORMS + UNBOOKED_DELIVERY_FORMS \
                and len(form.form.get("immunization_given", "")) > 0\
                and (len(pnc_forms) < 1 or (len(pnc_forms) > 0 and pnc_forms[0][0]._id == form._id)):
            _create_mcct_status_row(form._id, "eligible", form.domain, form.received_on.date(),
                                    registration_date, True, False, False)
            immunized = True
            save_indices.insert(0, index)

        elif form.xmlns in BOOKED_DELIVERY_FORMS + UNBOOKED_DELIVERY_FORMS \
                and form.form.get("pregnancy_outcome", "") == 'still_birth':
            _create_mcct_status_row(form._id, "eligible", form.domain, form.received_on.date(),
                                registration_date, False, False, True)
            save_indices.insert(0, index)

    for index in save_indices:
        del forms[index]
    for index in range(0, len(forms)):
        form = forms[index][0]
        registration_date = forms[index][1]
        status = "hidden" if index < len(forms) - 1 or immunized else "eligible"
        _create_mcct_status_row(form._id, status, form.domain, form.received_on.date(),
                                registration_date, False, False, False)


def handle_m4change_forms(sender, xform, cases, **kwargs):
    if hasattr(xform, "domain") and xform.domain in M4CHANGE_DOMAINS and hasattr(xform, "xmlns"):
        if xform.xmlns in ALL_M4CHANGE_FORMS:
            _handle_duplicate_form(xform, cases)
        if xform.xmlns in BOOKING_FORMS + BOOKED_DELIVERY_FORMS + UNBOOKED_DELIVERY_FORMS +\
                IMMUNIZATION_FORMS + FOLLOW_UP_FORMS:
            _filter_forms(xform, cases)


cases_received.connect(handle_m4change_forms)


def handle_fixture_location_update(sender, doc, diff, backend, **kwargs):
    if doc.get('doc_type') == 'XFormInstance' and doc.get('domain') in M4CHANGE_DOMAINS:
        xform = XFormInstance.wrap(doc)
        if hasattr(xform, "xmlns") and xform.xmlns in ALL_M4CHANGE_FORMS:
            location_id = xform.form.get("location_id", None)
            if not location_id:
                return
            client = get_redis_client()
            redis_key = REDIS_FIXTURE_KEYS[xform.domain]
            redis_lock_key = REDIS_FIXTURE_LOCK_KEYS[xform.domain]
            lock = get_redis_lock(redis_lock_key, timeout=5, name=redis_lock_key)
            if lock.acquire(blocking=True):
                try:
                    location_ids_str = client.get(redis_key)
                    location_ids = []
                    if location_ids_str:
                        location_ids = json.loads(location_ids_str)
                    if location_id not in location_ids:
                        location_ids.append(location_id)
                    client.set(redis_key, json.dumps(location_ids))
                finally:
                    release_lock(lock, True)


indicator_document_updated.connect(handle_fixture_location_update)
