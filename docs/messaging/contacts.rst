Contacts
========

A contact is a single person that we want to interact with through messaging. In CommCareHQ, at the time of
writing, contacts can either be users (CommCareUser, WebUser) or cases (CommCareCase).

In order for the messaging frameworks to interact with a contact, the contact must implement the
`corehq.apps.sms.mixin.CommCareMobileContactMixin <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/sms/mixin.py>`_.

Contacts have phone numbers which allows CommCareHQ to interact with them. All phone numbers for contacts
must be stored in International Format, and the frameworks always assume a phone number is given in
International Format.

Regarding the + sign before the phone number, the rule of thumb is to never store the + when storing
phone numbers, and to always display it when displaying phone numbers.

Users
^^^^^

A user's phone numbers are stored as the phone_numbers attribute on the CouchUser class, which is just a
list of strings.

At the time of writing, WebUsers are only allowed to have one-way phone numbers.

CommCareUsers are allowed to have two-way phone numbers, but in order to have a phone number be considered
to be a two-way phone number, it must first be verified. The verification process is initiated on the
edit mobile worker page and involves sending an outbound SMS to the phone number and having it be
acknowledged by receiving a validated response from it.

Cases
^^^^^

At the time of writing, cases are allowed to have only one phone number. The following case properties are
used to define a case's phone number:

contact_phone_number
    the phone number, in International Format

contact_phone_number_is_verified
    must be set to 1 in order to consider the phone number a two-way phone number; the point here is that
    the health worker registering the case should verify the phone number and the form should set this
    case property to 1 if the health worker has identified the phone number as verified

If two cases are registered with the same phone number and both set the verified flag to 1, it will only
be granted two-way phone number status to the case who registers it first.

If a two-way phone number can be granted for the case, a `corehq.apps.sms.models.PhoneNumber <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/sms/models.py>`_
entry with verified set to True is created for it. This happens automatically by running celery task
`run_case_update_rules_on_save <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/data_interfaces/tasks.py#L202>`_
for a case each time a case is saved.

Future State
^^^^^^^^^^^^

Forcing the verification workflows before granting a phone number two-way phone number status has proven to
be challenging for our users. In a (hopefully soon) future state, we will be doing away with all verification
workflows and automatically consider a phone number to be a two-way phone number for the contact who registers
it first.
