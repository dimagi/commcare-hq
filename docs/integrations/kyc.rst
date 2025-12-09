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
      "firstName": {
        "data_field": "first_name"
      },
      "lastName": {
        "data_field": "last_name"
      },
      "phoneNumber": {
        "data_field": "phone_number",
        "is_sensitive": true
      },
      "email": {
        "data_field": "email"
      },
      "nationalIdNumber": {
        "data_field": "national_id_number"
      },
      "streetAddress": {
        "data_field": "street_address"
      },
      "city": {
        "data_field": "city"
      },
      "postCode": {
        "data_field": "post_code"
      },
      "country": {
        "data_field": "country"
      }
    }

Each key in the JSON corresponds to a field name expected by the KYC provider. All keys are mandatory for MTN.
The `data_field` key within each mapping indicates the field in the recipient data store from which the value will be sourced.
The `is_sensitive` key, when set to `true`, marks the field as containing sensitive information and instructs the UI to hide it. If a field is not sensitive, this key can be omitted.
Let’s take a closer look at the Phone Number field in the above example:

- **phoneNumber**: The field name required by the MTN provider.
- **data_field:phone_number**: The field in the recipient data store from which the user’s phone number will be retrieved.
- **is_sensitive:true**: The phone number is considered sensitive and should be hidden in the UI.
