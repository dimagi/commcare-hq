#!/usr/bin/env bash
set -e

# source utils for logging functions log_group_{begin,end} and log_{success,fail}
source ./scripts/bash-utils.sh

log_group_begin "Check: translations"

pip install --upgrade pip
# install requirements, excluding difficult to install ones
grep -Ev 'xmlsec|python3-saml' requirements/dev-requirements.txt > ../requirements.txt
pip install -r ../requirements.txt

./scripts/make-translations.sh
git --no-pager diff
git update-index -q --refresh
if ! git diff-index --quiet HEAD --; then
    # Changes
    log_fail "Translations are inconsistent with code.  Did you run './scripts/make-translations.sh'?"
    git checkout -- locale/  # clean up
    exit 1
fi
# No changes
log_success "translations ok"
log_group_end  # only log group end on success (prevents group collapse on failure)
