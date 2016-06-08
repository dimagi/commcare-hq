FROM dimagi/commcarehq_base:latest

COPY mnt /mnt
VOLUME /mnt/commcare-hq-ro /mnt/lib
RUN groupadd -r cchq && useradd -r -g cchq cchq

ENTRYPOINT ["/mnt/run.sh"]
