---
  name: remove-feature-flag
  description: Remove a deprecated/frozen feature flag (toggle) from the CommCare HQ
  codebase. Audits usage, searches all references, removes toggle checks and the feature
  code, then removes the toggle definition. Interactive — confirms with user at each step.
  argument-hint: TOGGLE_NAME
  disable-model-invocation: true
  ---

  # Remove Feature Flag: `$ARGUMENTS`

  Remove the feature flag `$ARGUMENTS` from the codebase. The feature is being **deleted
  entirely** (toggle evaluates to `False`). Work through each phase interactively — present
  findings and get user confirmation before making changes.

  ## Phase 0: Configuration

  Before starting, load or create the configuration.

  1. **Try to read** `.claude/skills/remove-feature-flag/config.json` (relative to the repo
  root). If it exists and contains all required keys (`vellum_repo`, `worktree_base`,
  `branch_prefix`), load the values silently and skip to Phase 1.

  2. **If the config file is missing or incomplete**, auto-detect the values:

     - **Vellum repo**: Look for a directory named `vellum` containing `src/` with JS files
       in the parent directory of the repo root (i.e., a sibling directory). If not found,
       ask the user for the path using `AskUserQuestion`.

     - **Worktree base**: Default to `~/.claude/worktrees/commcare-hq`

     - **Branch prefix**: Run `git config user.name` and extract lowercase initials
       (e.g., "Amit Phulera" → "ap", "John Smith" → "js"). Default to empty string if
       undetectable.

  3. **Present the detected/default values** to the user using `AskUserQuestion` and ask them
  to confirm or provide overrides. For each value, show what was detected and let the user
  accept or type a different value.

  4. **Save the confirmed values** to `.claude/skills/remove-feature-flag/config.json`
     (relative to the repo root):
     ```json
     {
       "vellum_repo": "<confirmed path>",
       "worktree_base": "<confirmed path>",
       "branch_prefix": "<confirmed prefix>"
     }
     ```

  5. Use these values throughout all subsequent phases. Reference them as:
     - `REPO_ROOT` — the repository root directory (current working directory)
     - `VELLUM_REPO` — the Vellum repository path
     - `WORKTREE_BASE` — the worktree base directory
     - `BRANCH_PREFIX` — the branch name prefix (may be empty)

  The branch naming patterns are:
  - **Application code**: `{BRANCH_PREFIX}/remove-toggle/$ARGUMENTS` (or `remove-toggle/$ARGUMENTS` if BRANCH_PREFIX is empty)
  - **Migrations** (when model changes are needed): `{BRANCH_PREFIX}/remove-toggle/$ARGUMENTS-migrations` (or `remove-toggle/$ARGUMENTS-migrations` if BRANCH_PREFIX is empty)

  ## Phase 1: Identify & Audit

  1. Read `corehq/toggles/__init__.py` and find the variable
  `$ARGUMENTS`.

  2. Extract and present:
    - **Variable name**: `$ARGUMENTS`
    - **Slug**: the first string argument to the constructor
    - **Label**: the second string argument
    - **Tag**: TAG_DEPRECATED, TAG_FROZEN, etc.
    - **Type**: StaticToggle, PredictablyRandomToggle, DynamicallyPredictablyRandomToggle,
  FeatureRelease, etc.
    - **Namespaces**: NAMESPACE_DOMAIN, NAMESPACE_USER, etc.
    - **Description**: if provided
    - **parent_toggles**: if this toggle depends on others
    - **Dependent toggles**: search `parent_toggles=` for references to `$ARGUMENTS`

  3. **Provide commands for the user to look up domains with this flag enabled.** Do NOT run
  these commands automatically — they require switching virtualenvs and AWS authentication
  which is tricky to automate. Instead, present the commands for the user to run themselves:

    ```
    ## Verify domains with `$ARGUMENTS` enabled

    Please run the following commands to check which domains have this flag enabled.
    You'll need the `cchq` virtualenv activated:


    cchq production django-manage list_ff_domains <slug>
    cchq staging django-manage list_ff_domains <slug>
    cchq india django-manage list_ff_domains <slug>
    cchq eu django-manage list_ff_domains <slug>
    ```

    Also provide the admin links for manual verification:
    - `https://www.commcarehq.org/hq/flags/edit/<slug>/`
    - `https://staging.commcarehq.org/hq/flags/edit/<slug>/`
    - `https://india.commcarehq.org/hq/flags/edit/<slug>/`
    - `https://eu.commcarehq.org/hq/flags/edit/<slug>/`

  4. **Ask the user to verify** that no live/active domains depend on this feature.
  **Wait for user acknowledgment** before proceeding.

  ## Phase 2: Search All References

  Search for ALL of the following patterns. Use both the Python variable name (`$ARGUMENTS`)
  and its slug string. Present results grouped by category.

  ### Python references (`*.py` files, excluding tests)
  - `toggles.$ARGUMENTS` — catches `.enabled(`, `.enabled_for_request(`,
  `.required_decorator`, `.get_enabled_domains()`, `.set(`, and general references
  - The slug string in single or double quotes (e.g., `'the_slug'`)
  - `any_toggle_enabled(` calls that include `$ARGUMENTS`

  ### Django template references (`*.html` files)
  - `toggle_enabled:"<slug>"`

  ### JavaScript references (`*.js` files)
  - `toggleEnabled('<slug>')` or `toggleEnabled("<slug>")`

  ### Vellum references
  Search the Vellum repo at `VELLUM_REPO` for the toggle
  slug. Vellum receives HQ toggles via `toggles_dict()` as feature flags in its `features`
  object (see `corehq/apps/app_manager/views/formdesigner.py:_get_vellum_features`).

  Search patterns in Vellum `src/` directory:
  - `features.<slug>` or `features['<slug>']` or `features["<slug>"]`
  - The slug string in single or double quotes

  If found in Vellum, note these references — the Vellum code that checks this feature will
  become dead code and should be cleaned up (though Vellum changes require a separate PR in
  the Vellum repo). Present Vellum findings separately, put them is the PR description  and ask user how to handle them.

  ### Test references (`*.py` test files)
  - `flag_enabled('$ARGUMENTS')`
  - `flag_disabled('$ARGUMENTS')`

  ### Other
  - `parent_toggles=` in other toggle definitions that reference `$ARGUMENTS`
  - `STATIC_TOGGLE_STATES` in settings or environment config files for the slug

  Present a grouped summary:
  ```
  ## Reference Summary for $ARGUMENTS (slug: <slug>)

  ### Application code (N files):
    - path/file.py:123 — toggles.$ARGUMENTS.enabled(domain)
    ...

  ### Templates (N files):
    - path/template.html:45 — toggle_enabled:"slug"
    ...

  ### JavaScript (N files):
    - path/file.js:67 — toggleEnabled('slug')
    ...

  ### Vellum (N files):
    - src/file.js:89 — features.slug
    ...

  ### Tests (N files):
    - path/test_file.py:89 — @flag_enabled('$ARGUMENTS')
    ...

  ### Parent toggle dependencies (N):
    - OTHER_TOGGLE lists $ARGUMENTS in parent_toggles
    ...

  ### Toggle definition:
    - corehq/toggles/__init__.py:NNN
  ```

  **Wait for user acknowledgment** before proceeding.

  ### Two-branch determination

  Review the references found above. If removing the toggle will require **model field or
  attribute removals** (e.g., model fields, model properties, or model methods that exist solely
  for the flagged feature), the changes must be split into two branches:

  - **Application code branch** (`{BRANCH_PREFIX}/remove-toggle/$ARGUMENTS`): All toggle check
    removals, test updates, and toggle definition removal — no model/schema changes
  - **Migration branch** (`{BRANCH_PREFIX}/remove-toggle/$ARGUMENTS-migrations`): Model field/
    attribute removals and database migrations, based on top of the application code branch

  Present this determination to the user and confirm before proceeding. If no model changes are
  needed, proceed with a single branch as usual.

  ## Phase 3: Create Worktree & Make Changes — Sequential Commits

  Use a **git worktree** so multiple toggle removals can run in parallel without conflicting.

  1. Ensure the worktree base directory exists:
     ```bash
     mkdir -p WORKTREE_BASE
     ```

  2. Update master in the main repo and create the worktree:
     ```bash
     cd REPO_ROOT
     git fetch origin master
     git worktree add WORKTREE_BASE/$ARGUMENTS origin/master
     ```

  3. Create the branch in the worktree. First, check if the desired branch name already
     exists (locally or on the remote). If it does, append an incrementing number until an
     available name is found:
     ```bash
     cd WORKTREE_BASE/$ARGUMENTS
     # Determine available branch name
     BASE_BRANCH="BRANCH_PREFIX/remove-toggle/$ARGUMENTS"  # or "remove-toggle/$ARGUMENTS" if BRANCH_PREFIX is empty
     BRANCH="$BASE_BRANCH"
     COUNTER=1
     while git show-ref --verify --quiet "refs/heads/$BRANCH" || git show-ref --verify --quiet "refs/remotes/origin/$BRANCH"; do
       BRANCH="${BASE_BRANCH}${COUNTER}"
       COUNTER=$((COUNTER + 1))
     done
     git checkout -b "$BRANCH"
     ```
     Store the resolved branch name — use it for all subsequent git operations (push, PR).
     (If `BRANCH_PREFIX` is empty, use `remove-toggle/$ARGUMENTS` as the base branch name.)

  4. Initialize git submodules in the worktree (required for pytest pythonpath):
     ```bash
     cd WORKTREE_BASE/$ARGUMENTS
     git submodule update --init --recursive
     ```

  5. Copy `localsettings.py` from the main repo (gitignored but required for Django):
     ```bash
     cp REPO_ROOT/localsettings.py WORKTREE_BASE/$ARGUMENTS/localsettings.py
     ```

  6. Set up the Python virtual environment and install dependencies in the worktree:
     ```bash
     cd WORKTREE_BASE/$ARGUMENTS
     uv sync --extra testrunner
     source .venv/bin/activate
     yarn install --frozen-lockfile
     ```

  **All subsequent commands in Phase 3 and Phase 4 must run inside the worktree directory:**
  `WORKTREE_BASE/$ARGUMENTS` **with the `.venv` activated.**

  The feature is being **deleted entirely**. The toggle evaluates to `False`. Make changes
  in sequential commits, each leaving the app in a working state.

  **Migration note:** If any changes result in new database migrations, run
  `./manage.py makemigrations --lock-update` to generate the migration with the lock file
  updated. Commit migrations separately with a descriptive message.

  ### Commit 1: Remove toggle checks from application code

  Remove all toggle references from non-test Python files, templates, and JavaScript:

  | Pattern | Action |
  |---|---|
  | `if toggles.X.enabled():` body | Remove entire if-block (condition + body) |
  | `if not toggles.X.enabled():` body | Remove `if not`, keep body (dedent) |
  | `X.enabled() and other_condition` | Remove entire if-block |
  | `X.enabled() or other_condition` | Simplify to `if other_condition:` |
  | `@toggles.X.required_decorator()` | View is now inaccessible — remove view and its URL
  pattern, or ask user |
  | `@any_toggle_enabled(X, Y)` | Remove X from args; if one toggle remains, use that
  toggle's `.required_decorator()` |
  | `var = X.enabled()` | Replace with `var = False`, then simplify or inline |
  | `{% if request\|toggle_enabled:"slug" %}...{% endif %}` | Remove entire block |
  | `{% if request\|toggle_enabled:"slug" %}...{% else %}...{% endif %}` | Keep only
  else-branch content |
  | JS `if (toggles.toggleEnabled('slug'))` | Remove the block |
  | `parent_toggles=[..., X, ...]` | Ask user — child toggle may also need removal |

  **If using the two-branch strategy:** Do NOT remove model fields, model properties, or model
  methods in this commit. Only remove the toggle checks and simplify the application code. Model
  changes will be handled on the migration branch.

  Clean up unused imports in all modified files.

  **Commit cycle:**
  1. Make the changes (remove toggle checks, clean up unused imports)
  2. Commit: `Remove <TOGGLE_NAME> toggle checks from application code`
  3. Run `uv run isort <changed_files>` and `uv run flake8 <changed_files>` — fix any issues
  4. If isort/flake8 produced changes, commit separately: `Lint fixes after removing <TOGGLE_NAME> from application code`
  5. `uv run pytest <affected_test_files> -x` — fix any failures (commit fixes separately
  with a descriptive message)
  6. If any `.html` template files were changed, run `./manage.py build_bootstrap5_diffs` —
  if it produces changes, commit them separately: `Rebuild bootstrap5 diffs after removing <TOGGLE_NAME>`

  ### Commit 2: Update tests

  Remove toggle-related test decorators and context managers:

  | Pattern | Action |
  |---|---|
  | `@flag_enabled('$ARGUMENTS')` decorator | Remove decorator; if the test only tests the
  flagged feature, delete the entire test |
  | `@flag_disabled('$ARGUMENTS')` decorator | Remove decorator (feature is always disabled
  now, matching the mock) |
  | `with flag_enabled('$ARGUMENTS'):` | Remove the with-block and its body (feature is
  disabled, this code path doesn't execute) |
  | `with flag_disabled('$ARGUMENTS'):` | Remove `with`, keep body (dedent) |

  Clean up unused imports.

  **Commit cycle:**
  1. Make the changes (remove test decorators/context managers, clean up unused imports)
  2. Commit: `Remove <TOGGLE_NAME> from tests`
  3. Run `uv run isort <changed_files>` and `uv run flake8 <changed_files>` — fix any issues
  4. If isort/flake8 produced changes, commit separately: `Lint fixes after removing <TOGGLE_NAME> from tests`
  5. `uv run pytest <affected_test_files> -x` — fix any failures (commit fixes separately
  with a descriptive message)

  ### Commit 3: Comment out the toggle definition

  Comment out the `$ARGUMENTS` variable definition in `corehq/toggles/__init__.py` by
  prefixing each line of the definition with `# `. Do NOT delete the definition. This
  preserves the definition for reference during the review process while making it inactive.
  Clean up any now-unused imports (imports that were ONLY used by this toggle definition).

  **Commit cycle:**
  1. Make the change (comment out definition, clean up unused imports)
  2. Commit: `Comment out <TOGGLE_NAME> toggle definition`
  3. Run `uv run isort corehq/toggles/__init__.py` and `uv run flake8 corehq/toggles/__init__.py` — fix any issues
  4. If isort/flake8 produced changes, commit separately: `Lint fixes after commenting out <TOGGLE_NAME>`
  5. `uv run pytest corehq/toggles/ -x` — fix any failures (commit fixes separately
  with a descriptive message)

  ### Migration Branch (only if two-branch strategy)

  After completing all commits on the application code branch, create the migration branch.

  1. From the current worktree (still on the application code branch), create the migration
     branch based on the current HEAD:
     ```bash
     cd WORKTREE_BASE/$ARGUMENTS
     BASE_BRANCH="BRANCH_PREFIX/remove-toggle/$ARGUMENTS-migrations"  # or "remove-toggle/$ARGUMENTS-migrations" if BRANCH_PREFIX is empty
     BRANCH="$BASE_BRANCH"
     COUNTER=1
     while git show-ref --verify --quiet "refs/heads/$BRANCH" || git show-ref --verify --quiet "refs/remotes/origin/$BRANCH"; do
       BRANCH="${BASE_BRANCH}${COUNTER}"
       COUNTER=$((COUNTER + 1))
     done
     git checkout -b "$BRANCH"
     ```
     Store the resolved migration branch name.

  ### Commit 4: Remove model fields and attributes

  Remove the model fields, properties, and methods identified during Phase 2 that exist solely
  for the flagged feature. Clean up unused imports.

  **Commit cycle:**
  1. Make the changes (remove model fields/attributes, clean up unused imports)
  2. Commit: `Remove model fields for <TOGGLE_NAME>`
  3. Run `./manage.py makemigrations --lock-update` to generate migrations
  4. Commit migrations separately: `Add migrations for <TOGGLE_NAME> model field removal`
  5. Run `uv run isort <changed_files>` and `uv run flake8 <changed_files>` — fix any issues
  6. If isort/flake8 produced changes, commit separately: `Lint fixes for <TOGGLE_NAME> model removal`
  7. `uv run pytest <affected_test_files> -x` — fix any failures (commit fixes separately
  with a descriptive message)

  After completing the migration branch, switch back to the application code branch for
  verification:
  ```bash
  cd WORKTREE_BASE/$ARGUMENTS
  git checkout <APPLICATION_BRANCH_NAME>
  ```

  ## Phase 4: Final Verification & Re-review

  1. Grep for any remaining references to both the variable name and slug across the entire
  worktree codebase
  2. If references found, fix them and amend the appropriate commit

  3. **Thorough re-review of all changes.** Before proceeding to the PR, do a comprehensive
  review of every change made across all commits:

     a. Run `git diff origin/master...HEAD` in the worktree to see the full diff.

     b. Read through every changed file and verify:
        - All toggle checks were removed correctly (no half-removed conditionals, no dangling
          else-blocks, no orphaned variables)
        - Indentation and code flow are correct after block removal
        - No unrelated code was accidentally deleted or modified
        - Unused imports were cleaned up in every modified file
        - No new lint or syntax issues were introduced

     c. **Flag related but untouched code.** Look for code that is suspiciously related to the
        removed feature but was NOT behind a toggle check. Examples:
        - Helper functions, utility methods, or classes that were only called from the removed
          code paths and are now dead code
        - Template blocks, partials, or JS modules that were only rendered/used when the toggle
          was enabled
        - Model fields, database columns, or serializer fields that only existed for the flagged
          feature
        - URL patterns or API endpoints that are now unreachable after removing `required_decorator`
        - Constants, configuration values, or settings that were only used by the removed code
        - CSS classes or styles that only applied to the removed UI elements

     d. **Present findings to the user.** If any potentially related dead code is found:
        ```
        ## Re-review Findings

        The following code may be related to the removed feature but was not behind
        a toggle check. Please review whether these should also be removed:

        - path/file.py:123 — `helper_function()` is only called from removed code
        - path/models.py:45 — `FeatureModel` class appears unused after removal
        ...

        Would you like me to remove any of these?
        ```
        If the user confirms removals, make the changes and commit them separately with a
        descriptive message, then re-run lint and tests.

     e. If no issues or related dead code are found, confirm to the user that the re-review
        passed cleanly.

  **If using the two-branch strategy:** After verifying the application code branch, switch to
  the migration branch and perform the same re-review:
  ```bash
  git checkout <MIGRATION_BRANCH_NAME>
  git diff <APPLICATION_BRANCH_NAME>...HEAD
  ```
  Review all model changes and migrations for correctness. Then switch back to the application
  code branch when done.

  ## Phase 5: Summary & PR

  Present:
  - Number of commits, with files changed per commit
  - Toggle removed (variable name and slug)
  - Vellum references (if any) that need a separate PR

  Ask the user if they would like to create a PR. If yes:

  ### Application code PR

  1. Push the branch from the worktree (use the resolved branch name from Phase 3, step 3):
     ```bash
     cd WORKTREE_BASE/$ARGUMENTS
     git checkout <APPLICATION_BRANCH_NAME>
     git push -u origin <APPLICATION_BRANCH_NAME>
     ```
  2. Read the PR template at `.github/PULL_REQUEST_TEMPLATE.md`
  3. Create the PR as a draft using `gh pr create --draft` with:
    - Title: `Remove <TOGGLE_NAME> feature flag`
    - Body following the PR template, filling in each section appropriately:
      - **Product Description**: User-facing effects (usually none for flag removal)
      - **Technical Summary**: What was removed and from which files
      - **Feature Flag**: The toggle variable name, slug, and tag
      - **Safety story**: Why this change is safe (e.g. flag is deprecated, preserves default behavior)
      - **Automated test coverage**: Which tests cover the preserved behavior
      - **QA Plan**: Include `cchq` commands to verify no domains rely on the flag
      - **Migrations**: Remove this section (no migrations in this PR)
      - **Rollback instructions**: Typically safe to revert
      - **Labels & Review**: Leave checkboxes unchecked for the developer

  ### Migration PR (only if two-branch strategy)

  After creating the application code PR, push and create the migration PR:

  1. Push the migration branch:
     ```bash
     cd WORKTREE_BASE/$ARGUMENTS
     git checkout <MIGRATION_BRANCH_NAME>
     git push -u origin <MIGRATION_BRANCH_NAME>
     ```
  2. Create the migration PR as a draft using `gh pr create --draft` with:
    - Title: `Remove <TOGGLE_NAME> model fields and migrations`
    - Body following the PR template, filling in each section appropriately:
      - **Product Description**: Database cleanup — removes model fields that are no longer used
        after the toggle removal
      - **Technical Summary**: Which model fields were removed and the resulting migrations
      - **Feature Flag**: Same toggle variable name, slug, and tag
      - **Safety story**: Application code no longer references these fields (see application
        code PR). Link to the application code PR and note this PR should be merged after it.
      - **Automated test coverage**: Which tests cover the affected models
      - **QA Plan**: Verify migrations run cleanly
      - **Migrations**: List the generated migration files
      - **Rollback instructions**: Revert migrations, then revert this PR
      - **Labels & Review**: Leave checkboxes unchecked for the developer

  ## Phase 6: Cleanup Worktree

  After the PR is created (or if the user declines), offer to clean up the worktree:
  ```bash
  cd REPO_ROOT
  git worktree remove WORKTREE_BASE/$ARGUMENTS
  ```

  Only remove the worktree if the user confirms. The branch will still exist locally and
  on the remote.
