====================================
Project Standards and Best Practices
====================================

This document is a sumation of some of the standards and best practices that are followed in the design and implementation of the project to provide guidance and clarity for `implementers and contributors`_.

These standards are presented for clarity and convenience (to avoid arguments about style or judgement and document reasoning) but they are not intended to be comprehensive. Code reviewers will expect that industry-wide best practices are followed in addition to any specifically outlined concepts which are covered in this document. 

========
Security
========
The project's baseline security practices should be based on the latest recommendations from the Open Web Security Project (OWASP), which provides practical and evidence based standards for software implementers. If there is a question in approach on system design and OWASP has a stated position on the best approach, it should be expected that the OWASP sanctioned approach will be adopted.

In addition, the project follows the following specific security practices.

Security Protocols and Cryptography Implementation
--------------------------------------------------

The project strives for a high standard of technical and practical security, but it is not the intended purpose of the project to provide a novel technical approach to security.  Since there is an overwhelming consensus from security researchers and practitioners[1]_,[2]_ that it is a harmful practice for software systems attempt to implement their own unique security or cryptographic protocols, no such implementations will be adopted by the project.

Specifically, components of the project which externally authenticate users or secure data cryptographically will be:

- Based on a publicly documented specification or approach (Basic Authentication, OAuth, SAML, AES256, etc)
- In broad use in modern software with a practical basis of demonstrated success
- Adopted through the use of externaly implemented libraries or dependencies whenever practically possible

This expectation does not necessarily extend to code which is required for integrations which authenticate against external systems. Those implementations should always follow this approach when possible, and best practices should be maintained when managing secrets for such components.

.. [1] Jakob Jakobsen and Claudio Orlandi "On the CCA (in)security of MTProto." *Cryptology ePrint Archive, Report 2015/1177*

.. [2] Philipp Jovanovic and Samuel Neves "Dumb Crypto in Smart Grids: Practical Cryptanalysis of the Open Smart Grid Protocol." *Cryptology ePrint Archive, Report 2015/428*

.. _implementers and contributors: CONTRIBUTING.rst
