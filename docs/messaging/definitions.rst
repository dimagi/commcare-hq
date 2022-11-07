Messaging Definitions
=====================

General Messaging Terms
^^^^^^^^^^^^^^^^^^^^^^^

SMS Gateway
    a third party service that provides an API for sending and receiving SMS

Outbound SMS
    an SMS that is sent from the SMS Gateway to a contact

Inbound SMS
    an SMS that is sent from a contact to the SMS Gateway

Mobile Terminating (MT) SMS
    an outbound SMS

Mobile Originating (MO) SMS
    an inbound SMS

Dual Tone Multiple Frequencies (DTMF) tones:
    the tones made by a telephone when pressing a button such as number 1, number 2, etc.

Interactive Voice Response (IVR) Session:
    a phone call in which the user is prompted to make choices using DTMF tones and the flow of the call
    can change based on those choices

IVR Gateway
    a third party service that provides an API for handling IVR sessions

International Format (also referred to as E.164 Format) for a Phone Number:
    a format for a phone number which makes it so that it can be reached from any other country; the format
    typically starts with +, then the country code, then the number, though there may be some subtle
    operations to perform on the number before putting into international format, such as removing a leading
    zero

SMS Survey
    a way of collecting data over SMS that involves asking questions one SMS at a time and waiting for a
    contact's response before sending the next SMS

Structured SMS
    a way for collecting data over SMS that involves collecting all data points in one SMS rather than
    asking one question at a time as in an SMS Survey; for example: "REGISTER Joe 25" could be one way
    to define a Structured SMS that registers a contact named Joe whose age is 25.

Messaging Terms Commonly Used in CommCare HQ
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

SMS Backend
    the code which implements the API of a specific SMS Gateway

IVR Backend
    the code which implements the API of a specific IVR Gateway

Two-way Phone Number
    a phone number that the system has tied to a single contact in a single domain, so that the system
    can not only send oubound SMS to the contact, but the contact can also send inbound SMS and have
    the system process it accordingly; the system currently only considers a number to be two-way
    if there is a `corehq.apps.sms.models.PhoneNumber <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/sms/models.py>`_
    entry for it that has verified = True

One-way Phone Number
    a phone number that has not been tied to a single contact, so that the system can only send outbound
    SMS to the number; one-way phone numbers can be shared across many contacts in many domains, but only
    one of those numbers can be a two-way phone number
