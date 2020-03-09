Dependency Observatory


### Running

1. run `docker pull mozilla/dependencyscan:latest` to fetch the latest scanner image

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
