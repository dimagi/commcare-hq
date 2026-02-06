DET Exports API
===============

Overview
--------

Purpose:
    This API is intended for CommCare Data Pipeline to be able to list
    the Case and Form Exports available to the Data Export Tool, a.k.a.
    commcare-export, including the URL to download its config file.

Request URL:
    ``https://www.commcarehq.org/a/[domain]/api/det_export_instance/v1/``

Permission Required:
    View Reports


Response Details
----------------

The API response has an "objects" field. Each object includes the
following properties:

name:
    The name given by the user who created the export. For case
    exports, this defaults to the case type and the date the export
    was created.

type:
    "case" or "form"

export_format:
    The file format that the user chose to export data in. Most users
    choose "xlsx" for modern versions of Microsoft Excel, or "csv" for
    very large volumes of data.

is_deidentified:
    Whether personal ideintifiers are excluded from the export data.

case_type:
    (Case exports only) The case type of exported cases.

xmlns:
    (Form exports only) The XMLNS of exported forms.

det_config_url:
    The absolute URL where the Data Export Tool (DET) config file can be
    downloaded.

    This URL accepts API Key authentication, so the API client that is
    using this DET Exports API endpoint can also fetch the DET config
    file.


Example Output
~~~~~~~~~~~~~~

.. code-block:: json

    {
      "objects": [
        {
          "id": "a1b2c3",
          "name": "My Case Export",
          "type": "case",
          "export_format": "csv",
          "is_deidentified": false,
          "case_type": "stock",
          "xmlns": null,
          "det_config_url": "https://www.commcarehq.org/..."
        },
        {
          "id": "d4e5f6",
          "name": "My Form Export",
          "type": "form",
          "export_format": "xlsx",
          "is_deidentified": false,
          "case_type": null,
          "xmlns": "http://example.com/form1",
          "det_config_url": "https://www.commcarehq.org/..."
        }
      ]
    }
