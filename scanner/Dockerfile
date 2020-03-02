FROM python:3.8-slim-buster
ENV PYTHONUNBUFFERED 1
MAINTAINER https://github.com/mozilla-services/dependency-observatory

RUN groupadd --gid 1001 app && \
    useradd --uid 1001 --gid 1001 --shell /usr/sbin/nologin app

RUN DEBIAN_FRONTEND=noninteractive apt-get update && \
        apt-get upgrade -y && \
        apt-get install --no-install-recommends -y \
            apt-transport-https \
            ca-certificates \
            curl \
            gnupg2 \
            software-properties-common \
            build-essential \
            libpq-dev && \
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

RUN mkdir -p /app/src
WORKDIR /app/src

COPY requirements.txt .
COPY --from=dependency-observatory-db-common /src/ database/

RUN pip install --no-cache-dir --upgrade pip && \
        pip install --no-cache-dir -r requirements.txt -r database/requirements.txt

COPY src/ .

WORKDIR /app
USER app
ENV PYTHONPATH="/app/src/:${PYTHONPATH}"
CMD [ "python" ]
