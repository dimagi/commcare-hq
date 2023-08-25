# CommCare HQ Dependency Policy

We separate our dependencies based on environment, which ensures that
dependencies are not installed on an environment where they are not needed.

When adding new dependencies, consider what environment(s) require these
dependencies and make edits to the `.in` file(s) of the appropriate
environment(s).

After making these edits, you need to run
```.env
make requirements
```

`base-requirements` — Every environment, including tests and documentation,
requires these dependencies

`sso-requirements` — These requirements are needed for SSO and
are required by all environments that run CommCare HQ. This excludes one
environment, documentation, which cannot install these requirements.

`docs-requirements` — Requirements needed to run our Read The Docs build.

`test-requirements` — Requirements needed to run tests.

`dev-requirements` — Requirements only needed for local development.

`prod-requirements` — Requirements needed by all production &amp; staging environments.

## Pinning Dependencies

Our policy is that we don't pin dependencies that we don't have to pin. At minimum,
we might set a minimum required version.

Limited version pins are only used when absolutely needed and must be
accompanied by a comment.

If no comment is present next to a pinned version, we will assume that the
requirement was pinned unintentionally and members of the Dependency Pod
will remove that pin.
