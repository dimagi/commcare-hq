#!/usr/bin/env bash
set -e

echo "ICDS Setup"
if [[ -z "$encrypted_871d352bed27_key" || -z "$encrypted_871d352bed27_iv" ]]; then
    echo "Encryption keys missing. Skipping ICDS extension setup."
    exit 0
fi
openssl aes-256-cbc -K $encrypted_871d352bed27_key -iv $encrypted_871d352bed27_iv -in .travis/deploy_key.pem.enc -out .travis/deploy_key.pem -d
eval "$(ssh-agent -s)"
chmod 600 $TRAVIS_BUILD_DIR/.travis/deploy_key.pem
ssh-add $TRAVIS_BUILD_DIR/.travis/deploy_key.pem
mkdir -p $TRAVIS_BUILD_DIR/extensions/icds/
git clone git@github.com:dimagi/commcare-icds.git $TRAVIS_BUILD_DIR/extensions/icds/ --depth=1
cd $TRAVIS_BUILD_DIR/extensions/icds/ \
    && git fetch origin mk/extract-sensitive-vault-data \
    && git checkout mk/extract-sensitive-vault-data \
    || echo "Branch mk/extract-sensitive-vault-data not found in ICDS repo. Defaulting to 'master'"
cd $TRAVIS_BUILD_DIR
