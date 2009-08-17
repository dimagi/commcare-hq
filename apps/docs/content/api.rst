.. This period is necessary. The title doesn't show up unless we have something before it.
.. This is a django bug. The patch is here: http://code.djangoproject.com/ticket/4881
.. But let's not require patches to django

.

===================
COMMCAREHQ REST API
===================
If there are additional formats you would like us to support, feel free to email us at commcarehq-support@dimagi.com.

http://dev.commcarehq.org/api

* List all allowable api calls in XML

Schema
------

http://dev.commcarehq.org/api/xforms

* List all registered schemas. GET parameters can optionally specify:

  * format
  
    * allowable values: CSV, XML, JSON
    * default value: CSV
  * start-id
  
    * allowable value: any integer
  * end-id 
  
    * allowable value: any integer
  * start-submit-date
  
    * allowable value: date in the format YYYY-MM-DD
  * end-submit-date
  
    * allowable value: date in the format YYYY-MM-DD

http://dev.commcarehq.org/api/xforms/1/schema

 * Schema associated with the first registered schema. GET parameters can optionally specify:

  * format
  
    * allowable values: XML (XSD)
    * default value: XML (XSD)


Data
----
http://dev.commcarehq.org/api/xforms/1

* Data associated with the first registered schema. GET parameters can optionally specify:

  * format
  
    * allowable values: CSV, XML
    * default value: CSV
  * start-id
  
    * allowable value: any integer
  * end-id 
  
    * allowable value: any integer
  * start-submit-date
  
    * allowable value: date in the format YYYY-MM-DD
  * end-submit-date
  
    * allowable value: date in the format YYYY-MM-DD

http://dev.commcarehq.org/api/xforms/1/2

* Data associated with the second instance data submitted to the first registered schema. GET parameters can optionally specify:

  * format
  
    * allowable values: CSV, XML
    * default value: CSV


.. http://dev.commcarehq.org/api/xforms/1/2/attachment

.. * List all attachments associated with the second instance submitted to the first registered schema.

.. http://dev.commcarehq.org/api/xforms/1/2/attachment/3

.. * Download the third submitted attachment associated with the second instance data submitted to the first registered schema

Metadata
--------

http://dev.commcarehq.org/api/xforms/1/metadata

 * Metadata associated with the first registered schema. GET parameters can optionally specify:

  * format
  
    * allowable values: CSV, XML, JSON
    * default value: CSV
  * start-id
  
    * allowable value: any integer
  * end-id 
  
    * allowable value: any integer
  * start-submit-date
  
    * allowable value: date in the format YYYY-MM-DD
  * end-submit-date
  
    * allowable value: date in the format YYYY-MM-DD
    
http://dev.commcarehq.org/api/xforms/1/2/metadata

 * Metadata associated with the second submitted instance of the first registered schema.  GET parameters can optionally specify:

  * format
  
    * allowable values: CSV, XML, JSON
    * default value: CSV




A few examples
--------------

http://dev.commcarehq.org/api/xforms/1?format=xml&start-submit-date=2008-08-30

* Retrieve all data submitted after August 30, 2008, to the first registered schema
* Return the results in XML format

http://dev.commcarehq.org/api/xforms/1/2/metadata?format=JSON

* Retrieve the metadata associated with the second submission to the first registered schema
* Return the results in JSON

http://dev.commcarehq.org/api/xforms/1/2

* Retrieve the second submission to the first registered schema
* Return the results in the default format (CSV)
