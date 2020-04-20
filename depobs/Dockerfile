# dependency-observatory

FROM python:3.8-slim-buster

MAINTAINER https://github.com/mozilla-services/dependency-observatory

ENV PYTHONPATH $PYTHONPATH:/app
ENV PYTHONUNBUFFERED 1

ENV HOST 0.0.0.0
ENV PORT 8000
ENV FLASK_ENV "production"
ENV SQLALCHEMY_DATABASE_URI postgresql+psycopg2://pguser:pgpass@pghost/dbname
ENV CELERY_BROKER_URL sqla+postgresql://pguser:pgpass@pghost/dbname

RUN groupadd --gid 10001 app && \
    useradd --uid 10001 --gid 10001 --shell /usr/sbin/nologin app
RUN install -o app -g app -d /var/run/depobs /var/log/depobs

RUN DEBIAN_FRONTEND=noninteractive apt-get update && \
        apt-get upgrade -y && \
        apt-get install --no-install-recommends -y \
            apt-transport-https \
            ca-certificates \
            curl \
            gnupg2 \
            software-properties-common \
            build-essential \
            libpq-dev \
            graphviz \
	    jq \
            && \
        curl -fsSL https://download.docker.com/linux/debian/gpg | apt-key add - && \
        add-apt-repository \
            "deb [arch=amd64] https://download.docker.com/linux/debian \
            $(lsb_release -cs) \
            stable" && \
        DEBIAN_FRONTEND=noninteractive apt-get update && \
        apt-get install --no-install-recommends -y \
            docker-ce \
            docker-ce-cli \
            containerd.io

WORKDIR /app

COPY . depobs
RUN pip install --upgrade --no-cache-dir -r depobs/requirements.txt

USER app
ENTRYPOINT [ ]
CMD [ "python", "depobs/website/do.py" ]
