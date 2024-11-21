# syntax=docker/dockerfile:1

# This Dockerfile is built as the `dimagi/commcarehq_base` image, which
# is used for running tests.

FROM ghcr.io/astral-sh/uv:0.5.2-python3.9-bookworm-slim
MAINTAINER Dimagi <devops@dimagi.com>

ENV PYTHONUNBUFFERED=1 \
    PYTHONUSERBASE=/vendor \
    PATH=/vendor/bin:$PATH \
    NODE_VERSION=20.11.1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy
# UV_COMPILE_BYTECODE: Compile bytecode during installation to improve module
#   load performance. Also suppresses a couchdbkit syntax error that happens
#   during bytecode compilation.
# UV_LINK_MODE: Copy from the cache instead of linking since it's a mounted volume

RUN mkdir /vendor

RUN apt-get update \
  && apt-get install -y --no-install-recommends curl gnupg \
  && curl https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
  && sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list' \
  && apt-get update \
  && apt-get install -y --no-install-recommends \
     build-essential \
     bzip2 \
     default-jre \
     gettext \
     git \
     google-chrome-stable \
     libmagic1 \
     libpq-dev \
     libxml2 \
     libxmlsec1 \
     libxmlsec1-openssl \
     make \
  && rm -rf /var/lib/apt/lists/* /src/*.deb
# build-essential allows uv to build uwsgi; increases image size by 240 MB
# libpq-dev is for make-requirements-test.sh; increases image size by ~20 MB
# libpq-dev can be replaced with libpq5 if pip-tools is replaced with uv in make-requirements-test.sh

RUN curl -SLO "https://nodejs.org/dist/v$NODE_VERSION/node-v$NODE_VERSION-linux-x64.tar.gz" \
  && tar -xzf "node-v$NODE_VERSION-linux-x64.tar.gz" -C /usr/local --strip-components=1 \
  && rm "node-v$NODE_VERSION-linux-x64.tar.gz"

COPY requirements/test-requirements.txt package.json /vendor/

RUN --mount=type=cache,target=/root/.cache/uv \
  uv venv --allow-existing /vendor \
  && uv pip install --prefix=/vendor -r /vendor/test-requirements.txt

# this keeps the image size down, make sure to set in mocha-headless-chrome options
#   executablePath: 'google-chrome-stable'
ENV PUPPETEER_SKIP_DOWNLOAD true

RUN npm -g install \
    yarn \
    bower \
    grunt-cli \
    uglify-js \
    puppeteer \
    mocha-headless-chrome \
    sass \
 && cd /vendor \
 && npm shrinkwrap \
 && yarn global add phantomjs-prebuilt

# For backward compatibility with commcarehq_base image containing
# google-chrome-unstable. Can be removed after all test jobs with Gruntfile.js
# referencing google-chrome-unstable have completed (at least a few weeks or
# months after the PR in which this was introduced is merged). Old PRs can be
# updated to use google-chrome-stable by merging master into them.
RUN ln -s /usr/bin/google-chrome-stable /usr/bin/google-chrome-unstable
