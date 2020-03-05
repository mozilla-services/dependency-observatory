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
  * http://localhost:8000/package/foo (should 404)


1. check for loaded scan fixture data:

```console
docker-compose exec db psql -U postgres dependency_observatory
psql (12.1 (Debian 12.1-1.pgdg100+1))
Type "help" for help.

dependency_observatory=# \x on
Expanded display is on.
dependency_observatory=# SELECT name, version FROM package_versions ORDER BY inserted_at DESC LIMIT 3;
-[ RECORD 1 ]---------
name    | @hapi/bounce
version | 2.0.0
-[ RECORD 2 ]---------
name    | @hapi/lab
version | 22.0.3
-[ RECORD 3 ]---------
name    | babel-eslint
version | 10.1.0

dependency_observatory=# SELECT name, version, package_graphs.id, package_graphs.inserted_at FROM package_graphs INNER JOIN package_versions ON package_versions.id = package_graphs.root_package_version_id ORDER BY inserted_at DESC LIMIT 50;
-[ RECORD 1 ]---------------------------
name        | @hapi/bounce
version     | 2.0.0
id          | 4
inserted_at | 2020-03-05 17:49:47.310269
-[ RECORD 2 ]---------------------------
name        | @hapi/bounce
version     | 1.3.2
id          | 3
inserted_at | 2020-03-05 17:49:45.922996
-[ RECORD 3 ]---------------------------
name        | @hapi/bounce
version     | 1.3.1
id          | 2
inserted_at | 2020-03-05 17:49:44.414418
-[ RECORD 4 ]---------------------------
name        | @hapi/bounce
version     | 1.3.0
id          | 1
inserted_at | 2020-03-05 17:49:41.673835

```

NB: scan fixture loading runs with `docker-compose up`, but run `docker-compose run scan-fixture-loader` to load more data from `scanner/fixtures/postprocessed_repo_tasks.jsonl`
