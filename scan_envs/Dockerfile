ARG BASE_NAME
ARG BASE_VERSION=latest
FROM ${BASE_NAME}:${BASE_VERSION}

RUN groupadd --gid 10001 app && \
    useradd --uid 10001 --gid 10001 \
      --shell /usr/sbin/nologin \
      --home-dir /home/app/ app
RUN install -o app -g app -d /var/run/app /var/log/app /home/app

RUN apt-get -y update && apt-get install -y git jq ripgrep curl

RUN mkdir -p /opt
COPY docker-entrypoint.sh /opt

WORKDIR /home/app
USER app
ENTRYPOINT [ "/opt/docker-entrypoint.sh" ]
