KYC Integration Service
=======================

About
-----

The KYC Integration Service provides a seamless way to verify users through a KYC provider.
This service interacts with external KYC providers to handle identity verification.
Currently, only the `MTN KYC provider <https://developers.mtn.com/products/customer-kyc-verification>`_ is
supported. Additional providers may be added in the future.

Configuration
-------------
The configuration of the KYC service is done through a form that allows you to specify the following fields:

Recipient Data Store
~~~~~~~~~~~~~~~~~~~~
The **Recipient Data Store** field allows you to choose where the user data is available and where the results of KYC verification will be stored.

It supports the following options:

-  `User Custom Data <https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2143958236/Custom+User+Data>`_
-  `User Case <https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2143955258/User+Case+Management>`_
-  Other Case Type - Choose this option when user data is available in a different case type.

Other Case Type
~~~~~~~~~~~~~~~~~~~~
The **Other Case Type** field is used to specify the name of the case type to be used for the recipient data store.
This is available when **Recipient Data Store** is set to **Other Case Type**.

API Field to Recipient Data Map
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
This field allows you to map the fields provided by the KYC API to the fields in your recipient data store.
The mapping is expected to be in JSON format, allowing for flexible configuration.

Here is a sample configuration for the MTN provider.
::

    {
        "firstName": "first_name",
        "lastName": "last_name",
        "email": "email",
        "phoneNumber": "phone_number",
        "nationalIdNumber": "national_id_number",
        "streetAddress": "street_address",
        "city": "city",
        "postCode": "post_code",
        "country": "country"
    }

Each key in the JSON represents the field name expected by the KYC provider,
while the corresponding value represents the field in the recipient data store where the data will be sourced from.

Let’s take a closer look at the first field in the above example:

- **firstName**: The API field name for the MTN provider.
- **first_name**: The field in the recipient data store from which the data will be retrieved for the user.
