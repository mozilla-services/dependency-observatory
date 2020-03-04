# dependency-observatory

FROM python:3.7
MAINTAINER https://github.com/mozilla-services/dependency-observatory

RUN groupadd --gid 1001 app && \
    useradd --uid 1001 --gid 1001 --shell /usr/sbin/nologin app
RUN install -o app -g app -d /var/run/depobs /var/log/depobs

WORKDIR /app

COPY . depobs

RUN pip install --upgrade --no-cache-dir -r depobs/requirements.txt

ENV PYTHONPATH $PYTHONPATH:/app/depobs

ENV HOST 0.0.0.0
ENV PORT 8000
ENV DEBUG True
ENV DATABASE_URI postgresql+psycopg2://pguser:pgpass@pghost/dbname

USER app
CMD [ "flask", "run", "-h",  "0.0.0.0", "-p", "8000"]
