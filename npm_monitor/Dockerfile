ARG BUILD_FROM
FROM $BUILD_FROM

WORKDIR /app

# Instalace Pythonu a knihovny requests
RUN apk add --no-cache python3 py3-requests

# Kopírování našich skriptů do kontejneru
COPY run.sh /
COPY monitor.py /

# Nastavení práv ke spuštění
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]