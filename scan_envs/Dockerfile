ARG BASE_NAME
ARG BASE_VERSION=latest
FROM ${BASE_NAME}:${BASE_VERSION}

RUN groupadd --gid 10001 app && \
    useradd --uid 10001 --gid 10001 \
      --shell /usr/sbin/nologin \
      --home-dir /home/app/ app
RUN install -o app -g app -d /var/run/app /var/log/app /home/app

RUN DEBIAN_FRONTEND=noninteractive apt-get -y update && \
    apt-get install --no-install-recommends -y \
	    curl \
	    git \
	    ripgrep \
            apt-transport-https \
            ca-certificates \
            curl \
            gnupg

RUN echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] http://packages.cloud.google.com/apt cloud-sdk main" | \
    tee -a /etc/apt/sources.list.d/google-cloud-sdk.list && \
      curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | \
      apt-key --keyring /usr/share/keyrings/cloud.google.gpg  add - && \
      DEBIAN_FRONTEND=noninteractive apt-get update -y && \
      apt-get install google-cloud-sdk -y

RUN cargo --version && cargo install cargo-audit || true
RUN curl -L --proto '=https' --tlsv1.2 https://github.com/stedolan/jq/releases/download/jq-1.6/jq-linux64 -o /usr/bin/jq && chmod +x /usr/bin/jq

RUN mkdir -p /opt
COPY docker-entrypoint.sh /opt

WORKDIR /home/app
USER app
ENTRYPOINT [ "/opt/docker-entrypoint.sh" ]
