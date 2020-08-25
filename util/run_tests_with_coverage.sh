#!/bin/bash

CI=${CI:-""}
rm -rf htmlcov/

CONTAINER_NAME=${CONTAINER_NAME:-$(kubectl get pods -l io.kompose.service=api -o go-template --template '{{range .items}}{{.metadata.name}}{{"\n"}}{{end}}')}

kubectl exec -it "$CONTAINER_NAME" -- coverage run -m pytest -c /app/setup.cfg /app/tests /app/depobs/ "$@"
kubectl exec -it "$CONTAINER_NAME" -- coverage report
kubectl exec -it "$CONTAINER_NAME" -- coverage html
kubectl cp "${CONTAINER_NAME}:/tmp/htmlcov" "$(pwd)/htmlcov/"

if [[ "$CI" = "" ]]; then
    python -m webbrowser -t htmlcov/index.html
fi
