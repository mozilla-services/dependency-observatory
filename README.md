# Dependency Observatory

[![CircleCI](https://circleci.com/gh/mozilla-services/dependency-observatory.svg?style=svg)](https://circleci.com/gh/mozilla-services/dependency-observatory)

### Running

1. run `docker-compose up --build -d` to build and start DB, API, and scan runner worker

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

dependency_observatory=# SELECT * FROM npm_registry_entries ORDER BY inserted_at DESC LIMIT 1;
-[ RECORD 1 ]----------+-----------------------------------------------------------
id                     | 4
package_name           | @hapi/bounce
package_version        | 2.0.0
shasum                 | e6ef56991c366b1e2738b2cd83b01354d938cf3d
tarball                | https://registry.npmjs.org/@hapi/bounce/-/bounce-2.0.0.tgz
git_head               | 444a27bbe7e609d4ce05fc92206569766dc9ba38
repository_type        | git
repository_url         | git://github.com/hapijs/bounce.git
description            | Selective error catching and rewrite rules
url                    |
license_type           | BSD-3-Clause
license_url            |
keywords               | {error,catch}
has_shrinkwrap         | f
bugs_url               | https://github.com/hapijs/bounce/issues
bugs_email             |
author_name            |
author_email           |
author_url             |
maintainers            | [{"name": "hueniverse", "email": "eran@hammer.io"}]
contributors           | null
publisher_name         | hueniverse
publisher_email        | eran@hammer.io
publisher_node_version | 13.0.1
publisher_npm_version  | 6.12.0
published_at           | 2020-01-04 22:29:03.109
package_modified_at    | 2020-01-04 22:29:05.405
source_url             | https://registry.npmjs.org/@hapi/bounce
inserted_at            | 2020-03-05 18:34:06.506623
updated_at             |

dependency_observatory=# SELECT COUNT(1) FROM npmsio_scores;
-[ RECORD 1 ]
count | 256

dependency_observatory=#
```

NB: scan fixture loading runs with `docker-compose up`, but run `docker-compose run scan-fixture-loader` to load more data from files in `scanner/fixtures/`

1. visit API and start pages:

  * http://localhost:8000/static/index.html
  * http://localhost:8000/package/foo (should 404)

1. run `curl -X POST 'http://localhost:8000/scan?package_name=eslint&package_manager=npm'` to kick off a scan

### Local Development

Run:

```console
./util/write_version_json.sh > depobs/version.json
docker-compose up --build -d
```

#### API

Flask is configured with `FLASK_ENV=development`, which will reload on
valid python code changes.

### Worker tasks

The worker image mounts in local changes, but requires a restart to
reflect them.

Run `./util/call_task_in_worker.sh` with the task name and JSON-serialized args and kwargs. For example:

```console
./util/call_task_in_worker.sh add --args "[2,2]" --kwargs "{}"
Starting dependency-observatory-db ... done
running: celery -A depobs.worker.tasks call depobs.worker.tasks.add --args [2,2] --kwargs {}
3e8da0b9-7d9e-4e31-9a79-ec1e3987fc93

 -------------- celery@6e495a16cbc8 v4.4.2 (cliffs)

...

[tasks]
  . depobs.worker.tasks.add
  . depobs.worker.tasks.build_report_tree
  . depobs.worker.tasks.fetch_and_save_npmsio_scores
  . depobs.worker.tasks.fetch_and_save_registry_entries
  . depobs.worker.tasks.scan_npm_package
  . depobs.worker.tasks.scan_npm_package_then_build_report_tree
  . depobs.worker.tasks.score_package

[2020-03-27 17:35:07,131: INFO/MainProcess] Connected to sqla+postgresql://postgres:**@db/dependency_observatory
[2020-03-27 17:35:07,233: INFO/MainProcess] celery@6e495a16cbc8 ready.
[2020-03-27 17:35:07,244: INFO/MainProcess] Received task: depobs.worker.tasks.add[3e8da0b9-7d9e-4e31-9a79-ec1e3987fc93]
[2020-03-27 17:35:07,292: INFO/ForkPoolWorker-1] Task depobs.worker.tasks.add[3e8da0b9-7d9e-4e31-9a79-ec1e3987fc93] succeeded in 0.04597374200238846s: 4

worker: Warm shutdown (MainProcess)
```

### Deployment

1. fetch the relevant images e.g.

```console
docker pull mozilla/dependency-observatory:latest
```

1. Assuming a postgres database is accessible at
   `postgresql://pguser:pgpass@pghost/dbname`, run the following:

```console
export SQLALCHEMY_DATABASE_URI=postgresql+psycopg2://pguser:pgpass@pghost/dbname
export CELERY_BROKER_URL=sqla+postgresql://pguser:pgpass@pghost/dbname
export CELERY_RESULT_BACKEND=db+postgresql://pguser:pgpass@pghost/dbname

docker run -d --rm --name depobs-api -e "SQLALCHEMY_DATABASE_URI=$SQLALCHEMY_DATABASE_URI" -e "CELERY_BROKER_URL=$CELERY_BROKER_URL" -e "CELERY_RESULT_BACKEND=$CELERY_RESULT_BACKEND" -e "INIT_DB=1" -e "FLASK_APP=/app/depobs/website/do.py" -p 8000:8000 mozilla/dependency-observatory
docker run -d -u 0 --rm -v /var/run/docker.sock:/var/run/docker.sock --net=host --name dep-obs-worker -e "SQLALCHEMY_DATABASE_URI=$SQLALCHEMY_DATABASE_URI" -e "CELERY_BROKER_URL=$CELERY_BROKER_URL" -e "CELERY_RESULT_BACKEND=$CELERY_RESULT_BACKEND" mozilla/dependency-observatory /bin/bash -c "celery -A depobs.worker.tasks worker --loglevel=info"
```

Note that you'll probably want to derive from the image to properly deamonize the worker and web server.

### Scanning, Report Building, and Scoring Process

#### score computation

Scores are very much a work in progress. They attempt to capture:

1. how much code and how many people it trusts (# unique of dependencies, # unique of maintainers)
1. library's security track record
1. code quality and activity from npms.io score

It does not try to estimate the vulnerability reporting rate.

The current scoring proposal is described in: https://docs.google.com/document/d/10kmyjHkuy3GSQc7ZEfqbbTBS_w-p6l42DV5z3fC9twc/edit#

#### scoring and report building process

Described in:

* https://docs.google.com/document/d/1JhgeL11ro2_5Cmkgti-bN_juGVbVufQ50OOo3SOtcpE/edit
* https://github.com/mozilla-services/dependency-observatory/issues/130#issuecomment-608017713
