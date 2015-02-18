FROM debian:wheezy

MAINTAINER Charles Flèche <charles.fleche@free.fr>

RUN apt-get update \
 && apt-get -y install \
      libfreetype6-dev \
      libjpeg-dev \
      libpq-dev \
      libtiff-dev \
      libwebp-dev \
      libxml2-dev \
      libxslt-dev \
      postgresql-client \
      python-dev \
      python-pip \
      wget \
    && rm -rf /var/lib/apt/lists/*

RUN wget -O jdk.tar.gz --no-check-certificate --no-cookies --header "Cookie: oraclelicense=accept-securebackup-cookie" http://download.oracle.com/otn-pub/java/jdk/7u67-b01/jdk-7u67-linux-x64.tar.gz \
 && tar -xzf jdk.tar.gz \
 && mkdir -p /usr/lib/jvm \
 && mv ./jdk1.7.0* /usr/lib/jvm/jdk1.7.0 \
 && update-alternatives --install "/usr/bin/java" "java" "/usr/lib/jvm/jdk1.7.0/bin/java" 1 \
 && update-alternatives --install "/usr/bin/javac" "javac" "/usr/lib/jvm/jdk1.7.0/bin/javac" 1 \
 && update-alternatives --install "/usr/bin/javaws" "javaws" "/usr/lib/jvm/jdk1.7.0/bin/javaws" 1 \
 && update-alternatives --auto java

RUN pip install --upgrade pip

COPY requirements/requirements.txt /tmp/requirements.txt

RUN pip install -r /tmp/requirements.txt

WORKDIR /usr/src/commcare-hq

COPY . /usr/src/commcare-hq

RUN mv docker/localsettings.py localsettings.py

EXPOSE 8000

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
