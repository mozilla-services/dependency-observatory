Dependency Observatory


### Running

1. fetch scan images


```console
docker pull mozilla/dependencyscan:latest
```

1. build and start DB, API, and scanner runner worker

```console
docker-compose up --build -d
```

1. visit API and start pages:

  * http://localhost:8000/static/index.html
  * http://localhost:8000/package/foo
