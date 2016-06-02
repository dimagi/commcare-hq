FROM dimagi/commcarehq_base:latest

ENV PYTHONUNBUFFERED 1
COPY mnt /mnt
VOLUME /mnt/commcare-hq-ro /mnt/lib
WORKDIR /mnt

ENTRYPOINT ["/mnt/run.sh"]
