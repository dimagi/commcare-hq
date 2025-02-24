Application Structure API
=========================

Overview
---------

**Purpose**
    Retrieve either a specific application or a list of applications for a project, including their module, form, and case schemata. This supports linked applications.

**Base URL**

.. code-block:: text

    https://www.commcarehq.org/a/[domain]/api/[version]/application/[app_id]
    
*Omit* ``app_id`` *in the URL to retrieve a list of applications.*

Request & Response Details
---------------------------

**Input Parameters**

- ``extras``: *(boolean)* If ``true``, includes a dump of application data; otherwise, does not include additional data.

**Output Values**

The API response includes an ``objects`` field, which is a list of configurations for your applications. Each application object contains:

- ``name``: The name of the application.
- ``version``: The application version (build number).
- ``modules``: A list of modules with:

  - ``case_type``: The case type for the enclosing module.
  - ``case_properties``: A list of all case properties for the case type.
  - ``forms``: A list of all forms in the module.
  - ``questions``: A schema list for each question in the module.

- ``versions``: A list of application versions (builds) created from this application.
- Other application data, if ``extras`` is set to ``true``.

**Sample Output (JSON)**

.. code-block:: json

    {
      "meta": {
        "limit": 20,
        "next": null,
        "offset": 0,
        "previous": null,
        "total_count": 4
      },
      "objects": [
        {
          "id": "app uuid",
          "build_on": null,
          "build_comment": null,
          "is_released": false,
          "version": 16,
          "built_from_app_id": null,
          "name": "My application",
          "case_types": {
            "type_of_case_from_app_builder": [
              "case_prop1",
              "case_prop2"
            ]
          },
          "modules": [
            {
              "case_type": "type_of_case_from_app_builder",
              "forms": [
                {
                  "name": {
                    "en": "Name in English",
                    "es": "Nombre en Español"
                  },
                  "questions": [
                    {
                      "label": "The question",
                      "repeat": "",
                      "tag": "input",
                      "value": "/name_in_english/the_question"
                    }
                  ]
                }
              ]
            }
          ],
          "versions": [
            {
              "id": "app version uuid",
              "build_on": "2017-01-30T19:53:20",
              "build_comment": "",
              "is_released": true,
              "version": 16
            }
          ]
        }
      ]
    }
