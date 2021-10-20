How to use and reference forms and cases programatically
========================================================

With the introduction of the new architecture for form and case data it is now necessary to use
generic functions and accessors to access and operate on the models.

This document provides a basic guide for how to do that.

Models
------
In the codebase there are now two models for form and case data.

+------------------------+----------------------+
| Couch                  | SQL                  |
+========================+======================+
| CommCareCase           | CommCareCaseSQL      |
+------------------------+----------------------+
| CommCareCaseAction     | CaseTransaction      |
+------------------------+----------------------+
| CommCareCaseAttachment | CaseAttachmentSQL    |
+------------------------+----------------------+
| CommCareCaseIndex      | CommCareCaseIndexSQL |
+------------------------+----------------------+
|                        | XFormInstanceSQL     |
+------------------------+----------------------+
|                        | XFormOperationSQL    |
+------------------------+----------------------+

Some of these models define a common interface that allows you to perform the same operations
irrespective of the type. Some examples are shown below:

**Form Instance**

+------------------------------------+--------------------------------------------------+
| Property / method                  | Description                                      |
+====================================+==================================================+
| form.form_id                       | The instance ID of the form                      |
+------------------------------------+--------------------------------------------------+
| form.is_normal                     | Replacement for checking the doc_type of a form  |
|                                    |                                                  |
| form.is_deleted                    |                                                  |
|                                    |                                                  |
| form.is_archived                   |                                                  |
|                                    |                                                  |
| form.is_error                      |                                                  |
|                                    |                                                  |
| form.is_deprecated                 |                                                  |
|                                    |                                                  |
| form.is_duplicate                  |                                                  |
|                                    |                                                  |
| form.is_submission_error_log       |                                                  |
+------------------------------------+--------------------------------------------------+
| form.attachments                   | The form attachment objects                      |
+------------------------------------+--------------------------------------------------+
| form.get_attachment                | Get an attachment by name                        |
+------------------------------------+--------------------------------------------------+
| form.archive                       | Archive a form                                   |
+------------------------------------+--------------------------------------------------+
| form.unarchive                     | Unarchive a form                                 |
+------------------------------------+--------------------------------------------------+
| form.to_json                       | Get the JSON representation of a form            |
+------------------------------------+--------------------------------------------------+
| form.form_data                     | Get the XML form data                            |
+------------------------------------+--------------------------------------------------+


**Case**

+--------------------------------+---------------------------------------+
| Property / method              | Description                           |
+================================+=======================================+
| case.case_id                   | ID of the case                        |
+--------------------------------+---------------------------------------+
| case.is_deleted                | Replacement for doc_type check        |
+--------------------------------+---------------------------------------+
| case.case_name                 | Name of the case                      |
+--------------------------------+---------------------------------------+
| case.get_attachment            | Get attachment by name                |
+--------------------------------+---------------------------------------+
| case.dynamic_case_properties   | Dictionary of dynamic case properties |
+--------------------------------+---------------------------------------+
| case.get_subcases              | Get subcase objects                   |
+--------------------------------+---------------------------------------+
| case.get_index_map             | Get dictionary of case indices        |
+--------------------------------+---------------------------------------+

Model acessors
--------------
To access models from the database there are classes that abstract the actual DB operations.
These classes are generally names :code:`<type>Accessors` and must be instantiated with a domain
name in order to know which DB needs to be queried.

**Forms**

- FormAccessors(domain).get_form(form_id)
- FormAccessors(domain).get_forms(form_ids)
- FormAccessors(domain).iter_forms(form_ids)
- FormAccessors(domain).save_new_form(form)

  - only for new forms

- FormAccessors(domain).get_with_attachments(form)

  - Preload attachments to avoid having to the the DB again

**Cases**

- CaseAccessors(domain).get_case(case_id)
- CaseAccessors(domain).get_cases(case_ids)
- CaseAccessors(domain).iter_cases(case_ids)
- CaseAccessors(domain).get_case_ids_in_domain(type='dog')

**Ledgers**

- LedgerAccessors(domain).get_ledger_values_for_case(case_id)

For more details see:

* :code:`corehq.form_processor.interfaces.dbaccessors.FormAccessors`
* :code:`corehq.form_processor.interfaces.dbaccessors.CaseAccessors`
* :code:`corehq.form_processor.interfaces.dbaccessors.LedgerAccessors`


Unit Tests
----------
To create a form in unit tests use the following pattern::

    from corehq.form_processor.utils import get_simple_wrapped_form, TestFormMetadata

    def test_my_form_function(self):
        # This TestFormMetadata specifies properties about the form to be created
        metadata = TestFormMetadata(
            domain=self.user.domain,
            user_id=self.user._id,
        )
        form = get_simple_wrapped_form(
            form_id,
            metadata=metadata
        )

Creating cases can be done with the :code:`CaseFactory`::

    from casexml.apps.case.mock import CaseFactory

    def test_my_case_function(self):
        factory = CaseFactory(domain='foo')
        case = factory.create_case(
            case_type='my_case_type',
            owner_id='owner1',
            case_name='bar',
            update={'prop1': 'abc'}
        )

Cleaning up
~~~~~~~~~~~
Cleaning up in tests can be done using the :code:`FormProcessorTestUtils1` class::


    from corehq.form_processor.tests.utils import FormProcessorTestUtils

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases()
        # OR
        FormProcessorTestUtils.delete_all_cases(domain=domain)

        FormProcessorTestUtils.delete_all_xforms()
        # OR
        FormProcessorTestUtils.delete_all_xforms(domain=domain)



