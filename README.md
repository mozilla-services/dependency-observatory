# Dependency Observatory

[![CircleCI](https://circleci.com/gh/mozilla-services/dependency-observatory.svg?style=svg)](https://circleci.com/gh/mozilla-services/dependency-observatory)

Dependency Observatory is a web service for collecting data about open
source software dependencies (or package) and assessing how risky they
are to use.

**It is alpha software and subject to breaking changes.**

We're still working on package scores, but aim to capture the direct
and transitive impact of using a package on:

1. amount of code
1. number of maintainers and publishers trusted
1. code quality and chance of using vulnerabile code


## Architecture

Dependency Observatory consists of:

* a read-through cache for data from registries and other third party APIs
* an API for running analysis jobs in languages
* a web UI for starting analysis jobs and views package reports

### API and Routes

```
Endpoint                              Methods             Rule
------------------------------------  ------------------  ---------------------------------------------------------------------------------
views_blueprint.index_page            GET, HEAD, OPTIONS  /
dockerflow.heartbeat                  GET, HEAD, OPTIONS  /__heartbeat__
dockerflow.lbheartbeat                GET, HEAD, OPTIONS  /__lbheartbeat__
dockerflow.version                    GET, HEAD, OPTIONS  /__version__
views_blueprint.queue_scan            OPTIONS, POST       /api/v1/scans
views_blueprint.get_scan              GET, HEAD, OPTIONS  /api/v1/scans/<int:scan_id>
views_blueprint.read_scan_logs        GET, HEAD, OPTIONS  /api/v1/scans/<int:scan_id>/logs
views_blueprint.faq_page              GET, HEAD, OPTIONS  /faq
views_blueprint.render_job_logs       GET, HEAD, OPTIONS  /jobs/<string:job_name>/logs
views_blueprint.show_package_report   GET, HEAD, OPTIONS  /package_report
views_blueprint.get_condensate_graph  GET, HEAD, OPTIONS  /score_details/condensate_graphs/<int:graph_id>
views_blueprint.get_graph             GET, HEAD, OPTIONS  /score_details/graphs/<int:graph_id>
views_blueprint.get_scoring_graph     GET, HEAD, OPTIONS  /score_details/score_component_graph/<int:graph_id>/<string:package_report_field>
static                                GET, HEAD, OPTIONS  /static/<path:filename>
views_blueprint.get_statistics        GET, HEAD, OPTIONS  /statistics
```

### Analysis UI

1. user visits `/` and enters a package or dependency name to analysis
1. the UI makes a `HEAD` request with query params to see if a report
   exists
   e.g. `/package_report?package_manager=npm&package_name=%40hapi%2Fbounce&package_version=2.0.0`
1. if `/package_report` returns 200 UI redirects to the report page
   otherwise it makes a `POST /api/v1/jobs` to start an analysis job
1. shows logs for the analysis e.g. `/jobs/scan-score-npm-package-dffc9843/logs`
1. which redirects to `/package_report` when the analysis is successful

## Deploying

1. fetch the service container image:

```console
docker pull mozilla/dependency-observatory:latest
```

1. optionally, fetch images scan or analysis environment for the
   languages you're interseted in:

```
mozilla/dependency-observatory:rust-1
mozilla/dependency-observatory:node-10
mozilla/dependency-observatory:node-12
```

1. create a postgres database

1. modify [`kubernetes/deployment.yaml`](kubernetes/deployment.yaml)
   (e.g. remove DB point to your DB; update creds in DSN) then
   `kubectl create -f kubernetes/`


## Developing

### Running the service locally

See [`README.md` in `kubernetes/`](kubernetes/README.md) to run the
service on a local minikube cluster.

We also use `docker-compose` to build images, write unit tests, and
create database migrations.

### Running tests

* [`run_tests.sh`](util/run_tests.sh) runs tests the unit flag
  e.g. `-m unit` can be used to select tests that don't hit the DB or
  k8s API
* [`run_tests.sh`](util/run_tests_with_coverage.sh) runs tests and
  saves coverage output

### Developing worker jobs

#### Finding worker code

* `depobs/worker/main.py` is the main entry point
* `depobs/worker/tasks.py` houses code that requires database access
  for fetching data and scoring and kicking off analysis jobs
* `depobs/clients/` HTTP clients fetch data from third party APIs

#### Adding an analysis job

##### Analyzing untrusted code

NB: try [`util/run_cwd_in_image.sh`](util/run_cwd_in_image.sh)

1. add a scanning / analysis environment in `<langname>-<lang major
   version>` format to [`docker-compose.yml`](docker-compose.yml) or
   pick and existing one

1. add analysis steps (e.g. static (SAST) or dynamic analysis (DAST))
   to run in a scan_env to
   [`scan_envs/docker-entrypoint.sh`](scan_envs/docker-entrypoint.sh).
   They should an individual command as a CLI arg with env vars as
   keywords and output jsonlines http://jsonlines.org/

1. rebuild the image e.g. `docker-compose build node-12`

##### Saving analysis results

1. update [`depobs/worker/tasks.py`](depobs/worker/tasks.py) to start
   jobs to analyze untrusted code or fetch additional data and save
   the serialized results to the database (using
   `depobs/worker/serializers.py` or `depobs/models/`)

1. register the function as CLI command in [`depobs/worker/main.py`](depobs/worker/main.py)

1. start a shell on the API worker `kubectl exec -it api-<tab> --
/bin/bash` (NB: if you don't need to run kubernetes jobs,
`docker-compose exec api` will mount the CWD for faster development)

1. test the command e.g. with `python depobs/worker/main.py npm scan`

1. run to `kubectl exec -it svc/db -- /bin/bash -c 'su postgres -c
   "psql dependency_observatory"'` and inspect the database

##### Saving analysis results to the package report

1. In `depobs/database/models.py`, add a method to `PackageGraph` to fetch data and return a dict indexed by package id

1. In `depobs/worker/scoring.py`, add a class inheriting from
   `ScoreComponent` (see commends in `ScoreComponent` for details) to
   populate `PackageReport` fields froms the fetched data

1. Preview graphs with the `PackageReport` fields at
   `/score_details/score_component_graph/<int:graph_id>/<string:package_report_field>`

1. Add migrations to update the `score_view`, and `report_score_view`
   database views to add the data as a factor in scoring

1. If necessary, update `PackageScoreReport.report_json` and the UI to
   display and explain the new fields

### Developing the web server and API

#### Finding web code

Web server code can be found in `depobs/website/`.  Views currently
live in `depobs/website/views.py` and jinja2 templates in
`depobs/website/templates/`. It uses models from
`depobs/database/models.py` and calls out to code in other
directories.

#### Scripts

* [`flask_db.sh`](util/flask_db.sh) runs `flask db` on the docker-compose API instance to create migration scripts
* [`flask_routes.sh`](util/flask_routes.sh) prints out the current routes from the app
* [`flask_shell.sh`](util/flask_shell.sh) starts a flask shell in the API service pod

#### Formatting web resources

1. Run `docker-compose build format-web` then `docker-compose run
   format-web` to format. Edit the command docker-compose.yml to
   format resources other than `static/do.js` and `static/do.css`

### Adding a database migration

#### Autogenerating from changes to SQLAlchemy declarative metadata

1. run `docker-compose up -d api` if the api isn't already running with `docker-compose`

1. run `./util/flask_db.sh upgrade` to ensure your local database is up to date

1. autogenerate a migration script e.g. `./util/flask_db.sh migrate -m "add foo column to bar table"`
   to create a file with that message in `/migrations/versions`

1. run `sudo chown -vR $(whoami):$(whoami) migrations/versions` so root doesn't own the script

1. review and edit the script keeping in mind the limitations of
   alembic detecting changes
   https://alembic.sqlalchemy.org/en/latest/autogenerate.html#what-does-autogenerate-detect-and-what-does-it-not-detect

#### Adding a database view

1. run `docker-compose up -d api` if the api isn't already running with `docker-compose`

1. create an empty migration file e.g. `./util/flask_db.sh revision -m "add spam_view"`

1. run `sudo chown -vR $(whoami):$(whoami) migrations/versions` so root doesn't own the script

1. add an execute operation with the raw SQL (refer to existing view
   migration scripts)
   https://alembic.sqlalchemy.org/en/latest/ops.html#alembic.operations.Operations.execute

1. For programmatic access to the view, add a table with
   `__table_args__ = {"info": {"is_view": True}}` to the declarative
   table definition in `database/models.py` (to skip it in
   autogenerated migrations)

#### Review and test the migration

1. run `docker-compose up -d api` if the api isn't already running with `docker-compose`

1. run `./util/flask_db.sh upgrade --sql` and
   `./util/flask_db.sh downgrade --sql` and review the generated SQL

1. run upgrade then downgrade without `--sql` to make sure the
   migration applies without errors

1. commit the migration script to version control
