FROM dimagi/commcarehq_base:latest

COPY mnt /mnt
VOLUME /mnt/commcare-hq-ro /mnt/lib
WORKDIR /mnt

ENTRYPOINT ["/mnt/run.sh"]
