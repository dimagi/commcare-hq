FROM dimagi/commcarehq_py39:latest

VOLUME /mnt/commcare-hq-ro /mnt/lib
RUN ln -s /mnt/commcare-hq-ro/docker/run.sh /mnt/run.sh && \
    ln -s /mnt/commcare-hq-ro/docker/wait.sh /mnt/wait.sh && \
    groupadd -r cchq && useradd -r -g cchq cchq

RUN apt-get update \
  && apt-get install -y gettext
ENTRYPOINT ["/mnt/run.sh"]
