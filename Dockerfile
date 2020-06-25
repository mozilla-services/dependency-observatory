# dependency-observatory

FROM python:3.8-slim-buster

MAINTAINER https://github.com/mozilla-services/dependency-observatory

ENV PYTHONPATH $PYTHONPATH:/app
ENV PYTHONUNBUFFERED 1

ENV HOST 0.0.0.0
ENV PORT 8000
ENV FLASK_ENV "production"
ENV SQLALCHEMY_DATABASE_URI postgresql+psycopg2://pguser:pgpass@pghost/dbname

RUN groupadd --gid 10001 app && \
    useradd --uid 10001 --gid 10001 --shell /usr/sbin/nologin app
RUN install -o app -g app -d /var/run/depobs /var/log/depobs

RUN DEBIAN_FRONTEND=noninteractive apt-get update && \
        apt-get upgrade -y && \
        apt-get install --no-install-recommends -y \
            apt-transport-https \
            ca-certificates \
            build-essential \
            libpq-dev \
            graphviz \
            jq \
            curl

WORKDIR /app

COPY depobs/requirements.txt depobs/
RUN pip install --upgrade --no-cache-dir -r depobs/requirements.txt
COPY setup.cfg .
COPY pyproject.toml .
COPY migrations migrations
COPY bin bin
COPY depobs depobs

USER app
ENTRYPOINT [ "/app/bin/docker-entrypoint.sh" ]
CMD [ "web" ]
