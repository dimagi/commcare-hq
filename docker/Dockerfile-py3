FROM dimagi/commcarehq_py3_new:latest
# Based on docker/Dockerfile

VOLUME /mnt/commcare-hq-ro /mnt/lib
RUN ln -s /mnt/commcare-hq-ro/docker/run.sh /mnt/run.sh && \
    ln -s /mnt/commcare-hq-ro/docker/wait.sh /mnt/wait.sh && \
    groupadd -r cchq && useradd -r -g cchq cchq

ENTRYPOINT ["/mnt/run.sh"]
