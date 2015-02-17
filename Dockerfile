FROM debian:wheezy
MAINTAINER Charles Flèche <charles.fleche@free.fr>

RUN apt-get update \
 && apt-get -y install python-pip \
 && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip

COPY requirements/requirements.txt /tmp/requirements.txt

RUN apt-get update \
 && apt-get -y install \
      postgresql-client \
      libxml2-dev \
      libxslt-dev \
      libpq-dev \
      --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

RUN apt-get update \
 && apt-get -y install \
      python-dev \
      --no-install-recommends

RUN pip install -r /tmp/requirements.txt

WORKDIR /usr/src/commcare-hq

COPY . /usr/src/commcare-hq

RUN mv docker/localsettings.py localsettings.py

EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
