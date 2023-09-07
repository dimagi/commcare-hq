FROM dimagi/commcarehq_base:latest

VOLUME /mnt/commcare-hq-ro /mnt/lib
RUN ln -s /mnt/commcare-hq-ro/docker/run.sh /mnt/run.sh && \
    groupadd -r cchq && useradd -r -g cchq cchq

ENTRYPOINT ["/mnt/run.sh"]
