SMS Billables
#############

What is an SMSBillable
^^^^^^^^^^^^^^^^^^^^^^
An ``SmsBillable`` referred to here as a billable, is created for each message sent/received via a gateway.
The message contains all of the info necessary for the billable to determine the price of the message, which happens when the billable is created.

There are two methods used for determining the price of a billable.

- fetch the most relevant gateway fee based on the message's criteria
- fetch the price from an API if the backend supports it

Retrieve price from a gateway fee
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
An ``SMSGatewayFee`` contains price information (amount and currency) as well as a link to an ``SMSGatewayFeeCriteria`` object, referred to here as criteria.
The criteria enables us to link the message to the correct gateway fee, allowing for different prices based on things like country code or direction.

Retrieve price from an API
^^^^^^^^^^^^^^^^^^^^^^^^^^

The other means for determining the price is via an API if supported by the backend.
The backend has a flag ``using_api_to_get_fees``, however this does not mean all prices are determined via the API. See "Managing Gateway Fees" below.

The gateway fee will have priority over the API price, so if the message fits with a gateway fee's criteria the gateway fee will be used.

Managing Gateway Fees
^^^^^^^^^^^^^^^^^^^^^

If it is desired to use the API to fetch prices, a gateway fee must have its ``amount`` set to ``None``. This ensures the ``gateway_charge`` will use the ``direct_gateway_fee``.
