# CommCare HQ Dependency Policy

We separate our dependencies based on environment, which ensures that
dependencies are not installed on an environment where they are not needed.

When adding new dependencies, consider what environment(s) require these
dependencies and add them to the appropriate dependencies group in
pyproject.toml.

To add a new dependency run
```sh
uv add [--dev|--group=GROUP] PACKAGE_NAME
```

Alternately, manually add it to pyproject.toml. After a manual edit, run
```sh
uv lock
```

To pin a specific version in the lock file, run
```sh
uv lock --upgrade-package='PACKAGE_SPEC'
```

`dependencies` — Every environment, including tests and documentation,
requires these dependencies

`sso` — These requirements are needed for SSO and are required by all
environments that run CommCare HQ. This excludes one environment,
documentation, which cannot install these requirements.

`docs` — Requirements needed to run our Read The Docs build.

`test` — Requirements needed to run tests.

`dev` — Requirements only needed for local development.

`prod` — Requirements needed by all production &amp; staging environments.

## Pinning Dependencies

Our policy is that we don't pin dependencies that we don't have to pin. At minimum,
we might set a minimum required version.

Limited version pins are only used when absolutely needed and must be
accompanied by a comment.

If no comment is present next to a pinned version, we will assume that the
requirement was pinned unintentionally and members of the Dependency Pod
will remove that pin.
