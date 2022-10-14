FROM kaapstorm/commcarehq_incl:latest

VOLUME /mnt/lib
RUN ln -s /vendor/docker/run.sh /mnt/run.sh && \
    ln -s /vendor/docker/wait.sh /mnt/wait.sh && \
    groupadd -r cchq && useradd -r -g cchq cchq

ENTRYPOINT ["/mnt/run.sh"]
