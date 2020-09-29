
format:
	black .

format-web:
	docker-compose run format-web

type-check:
	mypy --config setup.cfg

build-image:
	./util/build_image.sh

build-scan-images:
	./util/build_scan_images.sh

redeploy:
	./util/redeploy_image.sh

recreate:
	./util/recreate_cluster.sh

port-forward:
	kubectl -n default port-forward svc/api 8000


api-shell:
	kubectl exec -it svc/api -- /bin/bash

db-shell:
	kubectl exec -it svc/db -- /bin/bash -c 'su postgres'

worker-shell:
	kubectl exec -it deployments/worker -- /bin/bash

api-flask-shell:
	kubectl exec -it svc/api -- /bin/bash -c 'flask shell'

worker-flask-shell:
	kubectl exec -it deployments/worker -- /bin/bash -c 'flask shell'

db-psql-shell:
	kubectl exec -it svc/db -- /bin/bash -c 'su postgres -c "psql dependency_observatory"'

# NB: not interactive no tty
db-save-json-results:
	kubectl exec svc/db -- /bin/bash -c 'su postgres -c "psql --csv -a dependency_observatory -c \"SELECT * FROM json_results\""' > json_results.csv

shellcheck:
	shellcheck bin/*.sh util/*.sh scan_envs/*.sh

unit-test:
	./util/run_tests.sh -m unit

unit-test-coverage:
	./util/run_tests_with_coverage.sh -m unit

test:
	./util/run_tests.sh

test-coverage:
	./util/run_tests_with_coverage.sh
