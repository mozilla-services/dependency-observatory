# dependency-observatory

FROM python:3.9.1-slim-buster

ENV PYTHONPATH $PYTHONPATH:/app
ENV PYTHONUNBUFFERED 1

ENV HOST 0.0.0.0
ENV PORT 8000
ENV FLASK_APP "depobs.website.wsgi:app"
ENV FLASK_ENV "production"
ENV SQLALCHEMY_DATABASE_URI postgresql+psycopg2://pguser:pgpass@pghost/dbname

RUN groupadd --gid 10001 app && \
    useradd --uid 10001 --gid 10001 --shell /usr/sbin/nologin app
RUN install -o app -g app -d /var/run/depobs /var/log/depobs

RUN DEBIAN_FRONTEND=noninteractive apt-get update && \
        apt-get upgrade -y && \
        apt-get install --no-install-recommends -y \
            apt-transport-https \
            build-essential \
            ca-certificates \
            curl \
            gnupg \
            graphviz \
            jq \
            libpcre3 libpcre3-dev \
            libpq-dev \
            mime-support

RUN echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] http://packages.cloud.google.com/apt cloud-sdk main" | \
    tee -a /etc/apt/sources.list.d/google-cloud-sdk.list && \
      curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | \
      apt-key --keyring /usr/share/keyrings/cloud.google.gpg  add - && \
      DEBIAN_FRONTEND=noninteractive apt-get update -y && \
      apt-get install google-cloud-sdk -y

WORKDIR /app

COPY depobs/requirements-dev.txt depobs/
COPY depobs/requirements.txt depobs/
RUN pip install --upgrade --no-cache-dir -r depobs/requirements.txt -r depobs/requirements-dev.txt
COPY setup.cfg .
COPY pyproject.toml .
COPY web-uwsgi.ini .
COPY worker-uwsgi.ini .
COPY migrations migrations
COPY bin bin
COPY depobs depobs
COPY version.json .
COPY tests tests

USER app
ENTRYPOINT [ "/app/bin/docker-entrypoint.sh" ]
CMD [ "web" ]
