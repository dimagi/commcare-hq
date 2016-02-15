App Tester
==========

The App Tester allows app builders to create simple tests for their forms. These tests are written in the YAML
document format, chosen for its legibility, and because app builders need nothing more than a simple text editor
to create tests. See below for an example.

The App Tester can be used from CommCareHQ, or remotely as a management command.

Sample Test
-----------

    # App Tester Example
    ---
    login:
      domain: example
      username: john.smith
      app: Case Management

    tests:
      - Mobile worker should be able to register a case:
          result: success
          modules:
            - Registration:
                forms:
                  - Registration:
                      answers:
                        - welcome_message:
                        - name: Joe Bloggs
                        - sample_choice_question: choice1
                        - sample_number_question: 1
      - An invalid choice should fail:
          result: error
          errorMessage: Invalid choice
          modules:
            - Registration:
                forms:
                  - Registration:
                      answers:
                        - welcome_message:
                        - name: Joe Bloggs
                        - sample_choice_question: choice1
                        - sample_number_question: 1
            - Follow Up:
                case: Joe Bloggs
                forms:
                  - Visit:
                      date: 2016-02-12
                      time: 12:00:00
                      answers:
                        - welcome_message:
                        - sample_choice_question: not_a_valid_choice
                        - sample_number_question: Sixty hundred eleventy and point six


Login details
-------------

In order for the App Tester to log in, you will need to give it the domain, app and mobile worker to log in as.


Tests
-----

Give each test a name that describes the expected behaviour it is testing, like "Mobile worker should be able to
register a case".

Use the key "case" to choose a case by its name for modules and forms that require a case.

You can also set the date and time if you want a form to be completed


Assertions
----------

Each test asserts a result. Possible values are:

* success: The test submits all forms successfully
* failure: The test fails to submit all forms
* error: More specific than just "failure". An error occurs. Add another key:
    * errorMessage: Set this to part, or all, of the error message
* assertCaseProperty: More specific that "success". Add the following keys:
    * caseType: The case type
    * caseName: The name of the case
    * casePropertyEquals: Its expected value
  In the future property comparisons beyond "Equals", like "GreaterThan" and "IsNotSet", can be added as they are
  needed or requested.


A Little Testing Philosophy for FMs
-----------------------------------

Bear in mind that, as with science, you are more interested in counter-examples than examples. In other words, you
certainly want to show that your app *can* work, but it is more important to test where it might break.
