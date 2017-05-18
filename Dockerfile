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

RUN wget -O jdk.tar.gz --quiet --no-check-certificate --no-cookies --header "Cookie: oraclelicense=accept-securebackup-cookie" http://download.oracle.com/otn-pub/java/jdk/7u67-b01/jdk-7u67-linux-x64.tar.gz \
 && tar -xzf jdk.tar.gz --absolute-names \
 && mkdir -p /usr/lib/jvm \
 && mv ./jdk1.7.0* /usr/lib/jvm/jdk1.7.0 \
 && update-alternatives --install "/usr/bin/java" "java" "/usr/lib/jvm/jdk1.7.0/bin/java" 1 \
 && update-alternatives --install "/usr/bin/javac" "javac" "/usr/lib/jvm/jdk1.7.0/bin/javac" 1 \
 && update-alternatives --install "/usr/bin/javaws" "javaws" "/usr/lib/jvm/jdk1.7.0/bin/javaws" 1 \
 && update-alternatives --auto java \
 && rm -f jdk.tar.gz

COPY requirements/requirements.txt \
     requirements/dev-requirements.txt \
     requirements/test-requirements.txt \
     package.json \
     /vendor/

# prefer https for git checkouts made by pip
RUN git config --global url."https://".insteadOf git:// \
 && pip install --upgrade pip \
 && pip install \
    -r requirements/requirements.txt \
    -r requirements/dev-requirements.txt \
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
