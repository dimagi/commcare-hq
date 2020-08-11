#!/usr/bin/env bash

RED='\033[0;31m'; ORANGE='\033[0;33m'; YELLOW='\033[1;33m'; COLOR_RESET='\033[0m'

echo "travis_fold:start:extension_setup"

echo "${YELLOW}ICDS Setup{$COLOR_RESET}"
if [[ -z "$encrypted_871d352bed27_key" || -z "$encrypted_871d352bed27_iv" ]]; then
    echo "${RED}Encryption keys missing. Skipping ICDS extension setup.${COLOR_RESET}"
    exit 0
openssl aes-256-cbc -K $encrypted_871d352bed27_key -iv $encrypted_871d352bed27_iv -in .travis/deploy_key.pem.enc -out .travis/deploy_key.pem -d
eval "$(ssh-agent -s)"
chmod 600 $TRAVIS_BUILD_DIR/.travis/deploy_key.pem
ssh-add $TRAVIS_BUILD_DIR/.travis/deploy_key.pem
mkdir -p $TRAVIS_BUILD_DIR/extensions/icds/
git clone git@github.com:dimagi/commcare-icds.git $TRAVIS_BUILD_DIR/extensions/icds/ --depth=1
cd $TRAVIS_BUILD_DIR/extensions/icds/ \
    && git fetch origin $TRAVIS_PULL_REQUEST_BRANCH \
    && git checkout $TRAVIS_PULL_REQUEST_BRANCH \
    || echo "{$ORANGE}Branch $TRAVIS_PULL_REQUEST_BRANCH not found in ICDS repo. Defaulting to 'master'{$COLOR_RESET}"
cd $TRAVIS_BUILD_DIR

echo "travis_fold:stop:extension_setup"
