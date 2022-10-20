FROM python:3.9
MAINTAINER Dimagi <devops@dimagi.com>

ENV PYTHONUNBUFFERED=1 \
    PYTHONUSERBASE=/vendor \
    PATH=/vendor/bin:$PATH \
    NODE_VERSION=14.19.1

RUN curl -SLO "https://nodejs.org/dist/v$NODE_VERSION/node-v$NODE_VERSION-linux-x64.tar.gz" \
  && tar -xzf "node-v$NODE_VERSION-linux-x64.tar.gz" -C /usr/local --strip-components=1 \
  && rm "node-v$NODE_VERSION-linux-x64.tar.gz"

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
     fonts-freefont-ttf \
     default-jdk \
     wget \
     libxml2-dev \
     libxmlsec1-dev \
     libxmlsec1-openssl \
     gettext

# Deletes all package sources, so don't apt-get install anything after this:
RUN rm -rf /var/lib/apt/lists/* /src/*.deb

RUN git clone -b nh/shared_files --depth 1 https://github.com/dimagi/commcare-hq.git /vendor

RUN ln -s /vendor/docker/run.sh /mnt/run.sh \
 && ln -s /vendor/docker/wait.sh /mnt/wait.sh \
 && groupadd -r cchq \
 && useradd -r -g cchq cchq

# prefer https for git checkouts made by pip
RUN git config --global url."https://".insteadOf git:// \
 && cd /vendor \
 && python3 -m venv venv \
 && . venv/bin/activate \
 && pip install --upgrade pip \
 && pip install pip-tools \
 && pip-sync requirements/test-requirements.txt \
 && rm -rf /root/.cache/pip

RUN npm -g install \
    yarn \
    bower \
    grunt-cli \
    uglify-js \
 && cd /vendor \
 && npm shrinkwrap \
 && yarn global add phantomjs-prebuilt

# this keeps the image size down, make sure to set in mocha-headless-chrome options
#   executablePath: 'google-chrome-unstable'
#ENV PUPPETEER_SKIP_DOWNLOAD=true
# ...
#    puppeteer \
#    mocha-headless-chrome \
#
# Skip puppeteer because this Docker image is not for running tests,
# and because of a new error that makes no sense to me:
#
#    **INFO** Skipping browser download. "PUPPETEER_SKIP_DOWNLOAD" environment variable was found.
#
#    > puppeteer@19.1.0 postinstall /usr/local/lib/node_modules/puppeteer
#    > node install.js
#
#    **INFO** Skipping browser download as instructed.
#    ERROR: Failed to set up Chromium r1045629! Set "PUPPETEER_SKIP_DOWNLOAD" env variable to skip download.
#    [Error: EACCES: permission denied, mkdir '/root/.cache/puppeteer/chrome'] {
#      errno: -13,
#      code: 'EACCES',
#      syscall: 'mkdir',
#      path: '/root/.cache/puppeteer/chrome'
#    }
#    npm ERR! code ELIFECYCLE
#    npm ERR! errno 1
#    npm ERR! puppeteer@19.1.0 postinstall: `node install.js`
#    npm ERR! Exit status 1
#    npm ERR!
#    npm ERR! Failed at the puppeteer@19.1.0 postinstall script.
#    npm ERR! This is probably not a problem with npm. There is likely additional logging output above.
#
#    npm ERR! A complete log of this run can be found in:
#    npm ERR!     /root/.npm/_logs/2022-10-24T13_22_49_922Z-debug.log

RUN rm -rf /root/.cache
