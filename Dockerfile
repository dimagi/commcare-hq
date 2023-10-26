# syntax=docker/dockerfile:1

# This Dockerfile is built as the `dimagi/commcarehq_base` image, which
# is used for running tests.

FROM python:3.9
MAINTAINER Dimagi <devops@dimagi.com>

ENV PYTHONUNBUFFERED=1 \
    PYTHONUSERBASE=/vendor \
    PATH=/vendor/bin:$PATH \
    NODE_VERSION=16.19.1

RUN mkdir /vendor

RUN curl -SLO "https://nodejs.org/dist/v$NODE_VERSION/node-v$NODE_VERSION-linux-x64.tar.gz" \
  && tar -xzf "node-v$NODE_VERSION-linux-x64.tar.gz" -C /usr/local --strip-components=1 \
  && rm "node-v$NODE_VERSION-linux-x64.tar.gz"

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
     default-jdk \
     wget \
     libxml2-dev \
     libxmlsec1-dev \
     libxmlsec1-openssl \
     gettext

# Install latest chrome dev package and fonts to support major
# charsets (Chinese, Japanese, Arabic, Hebrew, Thai and a few others)
# Note: this installs the necessary libs to make the bundled version
# of Chromium that Puppeteer installs, work.
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
  && sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list' \
  && apt-get update \
  && apt-get install -y --no-install-recommends \
     google-chrome-unstable \
     fonts-ipafont-gothic \
     fonts-wqy-zenhei \
     fonts-thai-tlwg \
     fonts-kacst \
     fonts-freefont-ttf

# Deletes all package sources, so don't apt-get install anything after this:
RUN rm -rf /var/lib/apt/lists/* /src/*.deb

COPY requirements/test-requirements.txt package.json /vendor/

# prefer https for git checkouts made by pip
RUN git config --global url."https://".insteadOf git:// \
 && pip install --upgrade pip \
 && pip install -r /vendor/test-requirements.txt --user --upgrade \
 && rm -rf /root/.cache/pip

# this keeps the image size down, make sure to set in mocha-headless-chrome options
#   executablePath: 'google-chrome-unstable'
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
