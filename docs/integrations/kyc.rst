KYC Integration Service
=======================

About
-----

The KYC Integration Service provides a seamless way to verify users through a KYC provider.
This service interacts with external KYC providers to handle identity verification.
Currently, the following KYC providers are supported:

- `MTN KYC provider <https://developers.mtn.com/products/customer-kyc-verification>`_
- `Orange Cameroon KYC provider <https://apiis.orange.cm/store/>`_

Additional providers may be added in the future.

Configuration
-------------
The configuration of the KYC service is done through a form that allows you to specify the following fields:

Provider
~~~~~~~~
The **Provider** field allows you to select which KYC provider to use for identity verification.
Currently supported providers are:

- **MTN KYC**: Uses the MTN Customer KYC Verification API
- **Orange Cameroon KYC**: Uses the Orange Cameroon API

Each provider has different required fields and configuration options as detailed below.

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

Stores Full Name (Orange Cameroon Only)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The **Stores Full Name** field is specific to the Orange Cameroon provider and appears only when:

- **Provider** is set to **Orange Cameroon KYC**, AND
- **Recipient Data Store** is set to **Other Case Type**

This boolean field determines how names are matched during verification:

- **Checked (True)**: The system expects a single ``fullName`` field in the recipient data store containing the complete name.
  The Orange API returns ``firstName`` and ``lastName`` separately, which are concatenated and compared against the user's ``fullName`` using an order-insensitive matching algorithm.
- **Unchecked (False)**: The system expects separate ``firstName`` and ``lastName`` fields in the recipient data store.
  Each field is compared individually against the corresponding API response.

API Field to Recipient Data Map
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
This field allows you to map the fields provided by the KYC API to the fields in your recipient data store.
The mapping is expected to be in JSON format, allowing for flexible configuration.

MTN Provider Configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^^
Here is a sample configuration for the MTN provider:
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
- **data_field:phone_number**: The field in the recipient data store from which the user's phone number will be retrieved.
- **is_sensitive:true**: The phone number is considered sensitive and should be hidden in the UI.

Orange Cameroon Provider Configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The Orange Cameroon provider requires fewer fields than MTN. The configuration depends on whether you're using the full name matching option.

**Configuration when Stores Full Name is disabled (default)**:
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
      }
    }

**Configuration when Stores Full Name is enabled**:
::

    {
      "fullName": {
        "data_field": "full_name"
      },
      "phoneNumber": {
        "data_field": "phone_number",
        "is_sensitive": true
      }
    }

Key points for Orange Cameroon:

- **phoneNumber**: Required for all Orange Cameroon configurations. Used to identify the customer in the API call.
- **firstName/lastName**: Required when Stores Full Name is disabled.
- **fullName**: Required when Stores Full Name is enabled. The system will match this against the concatenated firstName and lastName from the API using an order-insensitive algorithm.

Passing Threshold for KYC Verification
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
This field allows you to set the minimum score in percentage required for each field for a user to pass the KYC verification.
The value should be an integer between 0 and 100.
For MTN, the score is returned from the service provider for each field.
For Orange Cameroon, the score is calculated based on the similarity between the user data and the API response.

MTN Provider Threshold Configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Here is a sample configuration for the MTN provider:
::

    {
      "firstName": 90,
      "lastName": 90,
      "phoneNumber": 100,
      "emailAddress": 100,
      "nationalIdNumber": 100,
      "streetAddress": 80,
      "city": 100,
      "postCode": 100,
      "country": 100
    }

Each key in the JSON corresponds to a field name expected by the KYC provider. All keys are mandatory for MTN.
The value for each key indicates the minimum score required for that field for the user to pass the KYC verification.
Let’s take a closer look at the Phone Number field in the above example:

- **phoneNumber**: The field name required by the MTN provider.
- **100**: The value indicates that the user must have a score of 100 percent for the phone number field to pass the KYC verification.

Orange Cameroon Provider Threshold Configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The Orange Cameroon provider has simpler threshold requirements:

**Configuration when Stores Full Name is disabled (default)**:
::

    {
      "firstName": 90,
      "lastName": 90
    }

Both fields are required:

- **firstName**: The minimum matching score for the first name
- **lastName**: The minimum matching score for the last name

**Configuration when Stores Full Name is enabled**:
::

    {
      "fullName": 90
    }

Only one field is required:

- **fullName**: The minimum matching score for the full name

**Name Comparison Algorithm**
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
When comparing names using the full name matching option, the system employs an order-insensitive algorithm. This means that the order of the names does not matter during comparison.
For example, "John Doe" and "Doe John" would be considered a perfect match.

When comparing individual fields (first name and last name), the system performs a direct comparison of each field separately.

The algorithm used for calculating the similarity score between names is based on the **Levenshtein distance**, which measures the number of single-character edits required to change one string into another.

**Note**: It is important to ensure the passing thresholds are set appropriately to achieve the desired level of verification accuracy.