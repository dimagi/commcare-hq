.. |schemas| image:: ../static/docs/img/schemas.jpg
   :alt: schema screen shot
.. |reports| image:: ../static/docs/img/reports.jpg
   :alt: report screen shot
.. _CommCare Help Main Page: help_index

.. This period is necessary. The title doesn't show up unless we have something before it.
.. This is a django bug. The patch is here: http://code.djangoproject.com/ticket/4881
.. But let's not require patches to django

.

Schemas and Reports
===================
This is where you can view all the reports in the system broken down by XForm. If you decide to modify or create new XForms for CommCare, you can also register them with CommCare on this page.

|schemas|

To view all of the submissions for a given XForm, click on the "Display Name". 

* On the next page, you can see a list of all the submissions which conform to that XForm as well as all the raw data included in that form. 
* Questions that are not completed appear as "None" 
* Note that the data can be exported into Excel or any other data manipulation software of your choice

When you modify an existing XForm or create a new one:

* In the box marked "Register a New XForm", click "Choose File" and select the XForm you have created.
* Enter a "Display Name". This is a simple descriptive title which should help you to remember which form this is.
* Click Submit.

If the XForm parses correctly, you should see it added to the list of Registered XForms.
If not, you will receive an error message telling you what was wrong with the XForm you submitted. 


The following is an example of an automatically generated report.

|reports|


Return to the `CommCare Help Main Page`_