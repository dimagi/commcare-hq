What are these files?
=====================

This directory contains subdirectories for each supported version of
FHIR. Inside the directories are JSON schema files for all core resource
types.


How to support another FHIR version
-----------------------------------

#. Add the version to **corehq/motech/fhir/const.py**.

#. Download the "core" package from the `directory of FHIR specifications`_
   for the version you want. For example, for FHIR release R4, the core
   package is at http://hl7.org/fhir/hl7.fhir.r4.core.tgz . It contains
   JSON schema files for all core resource types in the **package/openapi/**
   directory.

#. Create a new subdirectory for the version name, in lower case, and
   place the JSON schema files in it. (The JSON files in the archive are
   marked executable. The last command corrects that.)

   .. code:: bash

      $ mkdir corehq/motech/fhir/json-schema/r4
      $ tar -xzf /path/to/hl7.fhir.r4.core.tgz package/openapi/ \
        --strip-components=2 \
        -C corehq/motech/fhir/json-schema/r4/
      $ chmod -x corehq/motech/fhir/json-schema/r4/*

#. In their original form, there are two aspects of the schema files
   that prevent them from being used to validate FHIR resource JSON
   documents:

   #. The schema's "id" value points to an HTTP URL that does not exist.
      It should point to the schema file.

   #. Some of the "$ref" values use resource type names, and some use
      schema filenames. They all need to use schema filenames.

   Use the ``fix-schema-files`` command in this directory to resolve
   those:

   .. code:: bash

      $ ./fix-schema-files r4/*


.. _directory of FHIR specifications: http://hl7.org/fhir/directory.html
