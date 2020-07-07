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

# Install latest chrome dev package and fonts to support major
# charsets (Chinese, Japanese, Arabic, Hebrew, Thai and a few others)
# Note: this installs the necessary libs to make the bundled version
# of Chromium that Puppeteer installs, work.
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
     openjdk-7-jdk \
     wget \
  && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
  && sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google.list' \
  && apt-get update \
  && apt-get install -y google-chrome-unstable fonts-ipafont-gothic fonts-wqy-zenhei fonts-thai-tlwg fonts-kacst ttf-freefont \
    --no-install-recommends \
  && rm -rf /var/lib/apt/lists/* /src/*.deb

COPY requirements/test-requirements.txt package.json /vendor/

# prefer https for git checkouts made by pip
RUN git config --global url."https://".insteadOf git:// \
 && pip install --upgrade pip \
 && pip install -r /vendor/test-requirements.txt --user --upgrade \
 && rm -rf /root/.cache/pip

# this keeps the image size down, make sure to set in mocha-headless-chrome options
#   executablePath: 'google-chrome-unstable'
ENV PUPPETEER_SKIP_CHROMIUM_DOWNLOAD true

RUN npm -g install \
    yarn \
    bower \
    grunt-cli \
    uglify-js \
 && npm -g install \
    puppeteer \
    mocha-headless-chrome \
 && echo '{ "allow_root": true }' > /root/.bowerrc \
 && cd /vendor \
 && npm shrinkwrap \
 && yarn global add phantomjs-prebuilt \
 && npm -g install
