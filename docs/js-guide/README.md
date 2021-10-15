# Dimagi JavaScript Guide

Dimagi's internal JavaScript guide for use in the CommCare HQ project.

Javascript code should be functional in all current major browsers, following the ECMAScript 2015 (ES6) standards, and should follow the guidelines described in this document.

## Table of contents

- [Static Files Organization](./code-organization.md)
- [Managing Dependencies](./dependencies.md)
   - [Historical Background on Module Patterns](./module-history.md)
   - [RequireJS Migration Guide](./migrating.md)
   - [Third Party Libraries](./libraries.md): usage and conventions of framework-level dependencies (jQuery, knockout, etc.)
   - [Installing external packages with yarn](./external-packages.md)
- [Server Integration Patterns](./integration-patterns.md) (toggles, i18n, etc.)
- [Production Static Files](./static-files.md) (collectstatic, compression, map files, CDN)
- [Testing](./testing.md)
- [Linting](./linting.md)
- [Inheritance](./inheritance.md)
