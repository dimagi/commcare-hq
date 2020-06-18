FROM python:3.6-jessie
MAINTAINER Dimagi <devops@dimagi.com>

ENV PYTHONUNBUFFERED=1 \
    PYTHONUSERBASE=/vendor \
    PATH=/vendor/bin:$PATH \
    NODE_VERSION=12.18.1

RUN mkdir /vendor

RUN curl -SLO "https://nodejs.org/dist/v$NODE_VERSION/node-v$NODE_VERSION-linux-x64.tar.gz" \
  && tar -xzf "node-v$NODE_VERSION-linux-x64.tar.gz" -C /usr/local --strip-components=1 \
  && rm "node-v$NODE_VERSION-linux-x64.tar.gz"

RUN apt-get update \
  && apt-get install -y \
  openjdk-7-jdk \
  apt-transport-https \
  ca-certificates \
  curl \
  gnupg \
  --no-install-recommends \
  && curl -sSL https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
  && echo "deb https://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
  && apt-get update && apt-get install -y \
  google-chrome-beta \
  fontconfig \
  fonts-ipafont-gothic \
  fonts-wqy-zenhei \
  fonts-thai-tlwg \
  fonts-kacst \
  fonts-noto \
  fonts-freefont-ttf \
  --no-install-recommends \
  && rm -rf /var/lib/apt/lists/*


COPY requirements/test-requirements.txt package.json /vendor/

# prefer https for git checkouts made by pip
RUN git config --global url."https://".insteadOf git:// \
 && pip install --upgrade pip \
 && pip install -r /vendor/test-requirements.txt --user --upgrade \
 && rm -rf /root/.cache/pip

RUN npm -g install \
    bower \
    grunt-cli \
    uglify-js \
 && export PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=false \
 && npm -g install \
    puppeteer \
    mocha-headless-chrome \
 && echo '{ "allow_root": true }' > /root/.bowerrc \
 && cd /vendor \
 && npm shrinkwrap \
 && npm -g install
