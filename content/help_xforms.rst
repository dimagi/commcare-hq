.. _CommCare Help Main Page: help_index

.. This period is necessary. The title doesn't show up unless we have something before it.
.. This is a django bug. The patch is here: http://code.djangoproject.com/ticket/4881
.. But let's not require patches to django

.


NAMESPACES
==========
**Note: The only mechanism by which CommCareHQ identifies a form is by its namespace (xmlns - short for XML NameSpace).**

We are currently working on a mechanisms for versioning. However this feature is not supported at this point in time, so revisions to any form should also include a unique namespace. For example, if you decide to modify a form with:

xmlns="http://dev.commcarehq.org/my_domain/my_form"

Then you should update the xmlns to be something like

xmlns="http://dev.commcarehq.org/my_domain/my_form/v0.2"

And re-register it on CommCareHQ at http://dev.commcarehq.org/xforms/register.



Modifying XForms
================
Most CommCare users want the flexibility to tweak and tune their XForms over the lifetime of a project. If this is something you choose to do, please **remember to re-register the XForm on CommCareHQ**.
There are a few steps involved in this process.

* Update your existing XForm. 
* Update the namespace (xmlns). This is the xmlns attribute attached to the top-level node within the <instance> element of your xform. For example:
    
  ::
  
       <instance>
           <top_level_node xmlns="http://dev.commcarehq.org/">
               <Meta>
		           <metadata>0.0.1</metadata>
               </Meta>
               <data />
           </top_level_node>
       </instance>

* Register the new xform at http://127.0.0.1:8000/xforms/


A few things to note:

* Re-registering the schema will cause all of the new data to be stored in a separate table than pre-existing forms. This is by design, since there is no 100% accurate way for CommCareHQ to guess how new fields map to old ones. 
* If you update the xform but do *not* change the schema, then we will do our best to parse your xform in compliance with the existing schema, discarding any data that does not match the schema. 



Do Not Change
=============
You should never change any of the elements under <Meta> in your xform, as these are a priori standards which CommCareHQ uses to create charts and graphs.


Changes That DO NOT Require Re-registration
===========================================
There are a few select changes that do not require re-registering the schema, which we list below. These are just general guidelines, and are not intended to be comprehensive. By far, the best way of knowing whether an update requires re-registration is to submit data using the new XForm and verify yourself that it shows up correctly on CommCareHQ.
**Remember: when in doubt, it is better to re-register the new schema!**

* Translations
* Changing the order of questions

Changes That DO Require Re-registration
=======================================
* Adding or removing fields from the <instance> element
* Renaming fields from the <instance> element
* Changing the <bind> 'type' of any element
* Changing the <bind> 'nodeset' of any element
* Adding or removing items from any 'select' 

Return to the `CommCare Help Main Page`_
