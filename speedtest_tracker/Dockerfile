ARG BUILD_FROM
FROM ${BUILD_FROM}

RUN apk add --no-cache python3 py3-requests

COPY run.py /
COPY run.sh /etc/services.d/speedtest_tracker/run

RUN chmod a+x /etc/services.d/speedtest_tracker/run