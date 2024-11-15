# DO NOT MERGE. TODO: configure automated build on hub.docker.com or revert to commcarehq_base
FROM dimagi/commcarehq-py39-uv:latest

VOLUME /mnt/commcare-hq-ro /mnt/lib
RUN ln -s /mnt/commcare-hq-ro/docker/run.sh /mnt/run.sh && \
    groupadd -r cchq && useradd -r -g cchq cchq

ENTRYPOINT ["/mnt/run.sh"]
