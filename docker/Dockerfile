FROM dimagi/commcarehq_base_new:latest
# When changing this file, also update docker/Dockerfile-py3

VOLUME /mnt/commcare-hq-ro /mnt/lib
RUN ln -s /mnt/commcare-hq-ro/docker/run.sh /mnt/run.sh && \
    ln -s /mnt/commcare-hq-ro/docker/wait.sh /mnt/wait.sh && \
    groupadd -r cchq && useradd -r -g cchq cchq

ENTRYPOINT ["/mnt/run.sh"]
