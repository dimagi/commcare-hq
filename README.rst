==========
HQ Auditor
==========

A set of simple auditing tools for HQ and its related technologies.

All audits events inherit from the AuditEvent model which contains some basic audit information.

What It does
============
- Log Views (NavigationEventAudit)
   - Directly with a view decorator
   - Centrally with a middelware and a settings parameter listing the fully qualified view names
- Centrally log model saves (ModelActionAudit) via attaching signals from a settings parameter
- Uses threadlocals for accessing the user in said signals
- Login/Logout and failed login attempts (AccessAudit)

Adding your own AuditEvent
==========================
#. Make a new model that inherits from AuditEvent
#. Make a classmethod for generating the audit event
#. Attach the auditevent to the AuditEvent manager (this will allow simple access to the audit methods without needing to import your namespaces)


