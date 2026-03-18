ARG BUILD_FROM
FROM $BUILD_FROM

WORKDIR /app

# Instalace Pythonu a knihovny requests
RUN apk add --no-cache python3 py3-requests

# Kopírování našich skriptů do kontejneru
COPY run.sh /app/run.sh
COPY monitor.py /app/monitor.py

# Nastavení práv ke spuštění
RUN chmod a+x /app/run.sh

CMD [ "/app/run.sh" ]