# dependency-observatory-tests

FROM mozilla/dependency-observatory:latest

WORKDIR /app

USER root
COPY . tests
RUN chown app /app -R

USER app
ENTRYPOINT [ ]
CMD [ "python", "depobs/website/do.py" ]
