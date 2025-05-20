# syntax=docker/dockerfile:1

# This Dockerfile is built as the `dimagi/commcarehq_base` image, which
# is used for running tests.

FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim
MAINTAINER Dimagi <devops@dimagi.com>

ENV PYTHONUNBUFFERED=1 \
    PYTHONUSERBASE=/vendor \
    PATH=/vendor/bin:$PATH \
    NODE_VERSION=20.11.1 \
    # Compile bytecode during installation to improve startup time. Also
    # suppresses a couchdbkit syntax error that happens during bytecode
    # compilation.
    UV_COMPILE_BYTECODE=1 \
    # Copy from the cache instead of linking since it's a mounted volume
    UV_LINK_MODE=copy \
    # Tell uv where to find pyproject.toml and uv.lock
    UV_PROJECT=/vendor \
    UV_PROJECT_ENVIRONMENT=/vendor

RUN mkdir /vendor

RUN apt-get update \
  && apt-get install -y --no-install-recommends curl gnupg \
  && curl https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
  && sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list' \
  && apt-get update \
  && apt-get install -y --no-install-recommends \
     # allows uv to build dependencies; increases image size by 240 MB
     build-essential \
     bzip2 \
     default-jre \
     gettext \
     git \
     google-chrome-stable \
     libmagic1 \
     libpq5 \
     # for xmlsec on Python 3.13
     libxml2-dev libxmlsec1-dev libxmlsec1-openssl pkg-config \
     # for `no-binary-package lxml` in pyproject.toml
     libz-dev \
     make \
  && rm -rf /var/lib/apt/lists/* /src/*.deb

RUN curl -SLO "https://nodejs.org/dist/v$NODE_VERSION/node-v$NODE_VERSION-linux-x64.tar.gz" \
  && tar -xzf "node-v$NODE_VERSION-linux-x64.tar.gz" -C /usr/local --strip-components=1 \
  && rm "node-v$NODE_VERSION-linux-x64.tar.gz"

COPY pyproject.toml uv.lock package.json /vendor/

RUN --mount=type=cache,target=/root/.cache/uv \
  uv sync --locked --group=test --no-dev --no-install-project

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
