SMS Backends
============

We have one SMS Backend class per SMS Gateway that we make available.

SMS Backends are defined by creating a new directory under `corehq.messaging.smsbackends <https://github.com/dimagi/commcare-hq/blob/master/corehq/messaging/smsbackends>`_,
and the code for each backend has two main parts:

* The outbound part of the backend which is represented by a class that subclasses
  `corehq.apps.sms.models.SQLSMSBackend <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/sms/models.py>`_

* The inbound part of the backend which is represented by a view that subclasses
  `corehq.apps.sms.views.IncomingBackendView <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/sms/views.py>`_


Outbound
^^^^^^^^

The outbound part of the backend code is responsible for interacting with the
SMS Gateway's API to send an SMS.

All outbound SMS backends are subclasses of SQLSMSBackend, and you can't use a
backend until you've created an instance of it and saved it in the database.
You can have multiple instances of backends, if for example, you have multiple
accounts with the same SMS gateway.

Backend instances can either be global, in which case they are shared by all
projects in CommCare HQ, or they can belong to a specific project. If belonged
to a specific project, a backend can optionally be shared with other projects
as well.

To write the outbound backend code:

#. Create a subclass of `corehq.apps.sms.models.SQLSMSBackend <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/sms/models.py>`_
   and implement the unimplemented methods:

    get_api_id
        should return a string that uniquely identifies the backend type (but
        is shared across backend instances); we choose to not use the class
        name for this since class names can change but the api id should never
        change; the api id is only used for sms billing to look up sms rates
        for this backend type
    get_generic_name
        a displayable name for the backend
    get_available_extra_fields
        each backend likely needs to store additional information, such as a
        username and password for authenticating with the SMS gateway; list
        those fields here and they will be accessible via the backend's config
        property
    get_form_class
        should return a subclass of `corehq.apps.sms.forms.BackendForm <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/sms/forms.py>`_,
        which should:

         * have form fields for each of the fields in get_available_extra_fields, and
         * implement the gateway_specific_fields property, which should return a
           crispy forms rendering of those fields
    send
        takes a `corehq.apps.sms.models.QueuedSMS <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/sms/models.py>`_
        object as an argument and is responsible for interfacing with the SMS
        Gateway's API to send the SMS; if you want the framework to retry the
        SMS, raise an exception in this method, otherwise if no exception is
        raised the framework takes that to mean the process was successful.
        Unretryable error responses may be recorded on the message object with
        `msg.set_gateway_error(message)` where `message` is the error message
        or code returned by the gateway.

#. Add the backend to settings.HQ_APPS and settings.SMS_LOADED_SQL_BACKENDS

#. Run ./manage.py makemigrations sms; Django will just create a proxy model
   for the backend model, but no database changes will occur

#. Add an outbound test for the backend in `corehq.apps.sms.tests.test_backends <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/sms/tests/test_backends.py>`_.
   This will test that the backend is reachable by the framework, but any
   testing of the direct API connection with the gateway must be tested
   manually.

Once that's done, you should be able to create instances of the backend by
navigating to Messaging -> SMS Connectivity (for domain-level backend
instances) or Admin -> SMS Connectivity and Billing (for global backend
instances). To test it out, set it as the default backend for a project and try
sending an SMS through the Compose SMS interface.

Things to look out for:

* Make sure you use the proper encoding of the message when you implement the
  send() method. Some gateways are picky about the encoding needed. For
  example, some require everything to be UTF-8. Others might make you choose
  between ASCII and Unicode. And for the ones that accept Unicode, you might
  need to sometimes convert it to a hex representation. And remember that
  get/post data will be automatically url-encoded when you use python requests.
  Consult the documentation for the gateway to see what is required.

* The message limit for a single SMS is 160 7-bit structures. That works out to
  140 bytes, or 70 words. That means the limit for a single message is
  typically 160 GSM characters, or 70 Unicode characters. And it's actually a
  little more complicated than that since some simple ASCII characters (such as
  '{') take up two GSM characters, and each carrier uses the GSM alphabet
  according to language.

  So the bottom line is, it's difficult to know whether the given text will fit
  in one SMS message or not. As a result, you should find out if the gateway
  supports Concatenated SMS, a process which seamlessly splits up long messages
  into multiple SMS and stiches them back up without you having to do any
  additional work. You may need to have the gateway enable a setting to do this
  or include an additional parameter when sending SMS to make this work.

* If this gateway has a phone number that people can reply to (whether a long
  code or short code), you'll want to add an entry to the sms.Phoneblacklist
  model for the gateway's phone number so that the system won't allow sending
  SMS to this number as a precaution. You can do so in the Django admin, and
  you'll want to make sure that send_sms and can_opt_in are both False on the
  record.

Inbound
^^^^^^^

The inbound part of the backend code is responsible for exposing a view which
implements the API that the SMS Gateway expects so that the gateway can connect
to CommCare HQ and notify us of inbound SMS.

To write the inbound backend code:

#. Create a subclass of `corehq.apps.sms.views.IncomingBackendView <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/sms/views.py>`_,
   and implement the unimplemented property:

   backend_class
       should return the subclass of SQLSMSBackend that was written above

#. Implement either the get() or post() method on the view based on the
   gateway's API. The only requirement of the framework is that this method call
   the `corehq.apps.sms.api.incoming <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/sms/api.py>`_
   function, but you should also:

    * pass self.backend_couch_id as the backend_id kwarg to incoming()
    * if the gateway gives you a unique identifier for the SMS in their system,
      pass that identifier as the backend_message_id kwarg to incoming(); this
      can help later with debugging

#. Create a url for the view. The url pattern should accept an api key and look
   something like: r'^sms/(?P<api_key>[\w-]+)/$' . The API key used will need
   to match the inbound_api_key of a backend instance in order to be processed.

#. Let the SMS Gateway know the url to connect to, including the API Key. To get
   the API Key, look at the value of the inbound_api_key property on the
   backend instance. This value is generated automatically when you first
   create a backend instance.

What happens behind the scenes is as follows:

#. A contact sends an inbound SMS to the SMS Gateway

#. The SMS Gateway connects to the URL configured above.

#. The view automatically looks up the backend instance by api key and rejects
   the request if one is not found.

#. Your get() or post() method is invoked which parses the parameters
   accordingly and passes the information to the inbound incoming() entry
   point.

#. The Inbound SMS framework takes it from there as described in the Inbound SMS
   section.

NOTE: The api key is part of the URL because it's not always easy to make the
gateway send us an extra arbitrary parameter on each inbound SMS.

Rate Limiting
^^^^^^^^^^^^^

You may want (or need) to limit the rate at which SMS get sent from a given
backend instance. To do so, just override the get_sms_rate_limit() method in
your SQLSMSBackend, and have it return the maximum number of SMS that can be
sent in a one minute period.

Load Balancing
^^^^^^^^^^^^^^

If you want to load balance the Outbound SMS traffic automatically across
multiple phone numbers, do the following:

#. Make your BackendForm subclass the `corehq.apps.sms.forms.LoadBalancingBackendFormMixin <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/sms/forms.py>`_

#. Make your SQLSMSBackend subclass the `corehq.apps.sms.models.PhoneLoadBalancingMixin <https://github.com/dimagi/commcare-hq/blob/master/corehq/apps/sms/models.py>`_

#. Make your SQLSMSBackend's send method take a orig_phone_number kwarg. This
   will be the phone number to use when sending. This is always sent to the
   send() method, even if there is just one phone number to load balance over.

From there, the framework will automatically handle managing the phone numbers
through the create/edit gateway UI and balancing the load across the numbers
when sending. When choosing the originating phone number, the destination
number is hashed and that hash is used to choose from the list of load
balancing phone numbers, so that a recipient always receives messages from the
same originating number.

If your backend uses load balancing and rate limiting, the framework applies
the rate limit to each phone number separately as you would expect.

Backend Selection
^^^^^^^^^^^^^^^^^

There's also an **Automatic Choose** option, which selects a backend for each message based on the
phone number's prefix. Domains can customize their prefix mappings, and there's a global mapping that
HQ will fall back to if no domain-specific mapping is defined.

These prefix-backend mappings are stored in ``SQLMobileBackend``. The global mappings can be accessed with
``[(m.prefix, m.backend) for m in SQLMobileBackendMapping.objects.filter(is_global=True)]``

On production, this currently returns

.. code-block:: python

    ('27', <SQLMobileBackend: Global Backend 'GRAPEVINE-ZA'>),
    ('999', <SQLMobileBackend: Global Backend 'MOBILE_BACKEND_TEST'>),
    ('1', <SQLMobileBackend: Global Backend 'MOBILE_BACKEND_TWILIO'>),
    ('258', <SQLMobileBackend: Global Backend 'MOBILE_BACKEND_MOZ'>),
    ('266', <SQLMobileBackend: Global Backend 'GRAPEVINE-ZA'>),
    ('265', <SQLMobileBackend: Global Backend 'MOBILE_BACKEND_TWILIO'>),
    ('91', <SQLMobileBackend: Global Backend 'MOBILE_BACKEND_UNICEL'>),
    ('268', <SQLMobileBackend: Global Backend 'GRAPEVINE-ZA'>),
    ('256', <SQLMobileBackend: Global Backend 'MOBILE_BACKEND_YO'>),
    ('*', <SQLMobileBackend: Global Backend 'MOBILE_BACKEND_MACH'>)
