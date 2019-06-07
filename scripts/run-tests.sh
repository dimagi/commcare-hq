#! /usr/bin/env bash

set -ex  # fail fast, print commands as they are executed

[[ "$TEST_MAKE_REQUIREMENTS" == "yes" ]] && scripts/test-make-requirements.sh

scripts/docker test --noinput --stop --verbosity=2 --divide-depth=1 --with-timing --threshold=10
