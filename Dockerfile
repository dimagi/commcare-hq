# When changing this file, also update Dockerfile-py3
FROM python:2.7
MAINTAINER Dimagi <devops@dimagi.com>

ENV PYTHONUNBUFFERED=1 \
    PYTHONUSERBASE=/vendor \
    PATH=/vendor/bin:$PATH \
    NODE_VERSION=5.12.0

RUN mkdir /vendor

RUN curl -SLO "https://nodejs.org/dist/v$NODE_VERSION/node-v$NODE_VERSION-linux-x64.tar.gz" \
  && tar -xzf "node-v$NODE_VERSION-linux-x64.tar.gz" -C /usr/local --strip-components=1 \
  && rm "node-v$NODE_VERSION-linux-x64.tar.gz"

RUN apt-get update && apt-get install -y --no-install-recommends openjdk-7-jdk

COPY requirements/requirements.txt \
     requirements/dev-requirements.txt \
     requirements/test-requirements.txt \
     package.json \
     /vendor/

# prefer https for git checkouts made by pip
RUN git config --global url."https://".insteadOf git:// \
 && pip install --upgrade pip \
 && pip install \
    -r /vendor/requirements.txt \
    -r /vendor/dev-requirements.txt \
    --user --upgrade \
 && rm -rf /root/.cache/pip

RUN npm -g install \
    bower \
    grunt-cli \
    uglify-js \
 && echo '{ "allow_root": true }' > /root/.bowerrc \
 && cd /vendor \
 && npm shrinkwrap \
 && npm -g install \
 && npm cache clean
