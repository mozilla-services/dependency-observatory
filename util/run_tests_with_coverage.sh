#!/bin/bash

CI=${CI:-""}
rm -rf htmlcov/

CONTAINER_NAME=${CONTAINER_NAME:-$(kubectl get pods -l io.kompose.service=api -o go-template --template '{{range .items}}{{.metadata.name}}{{"\n"}}{{end}}')}

kubectl cp tests/ "${CONTAINER_NAME}:/tmp/"
kubectl exec -it "$CONTAINER_NAME" -- coverage run -m pytest /tmp/tests "$@"
kubectl exec -it "$CONTAINER_NAME" -- coverage report
kubectl exec -it "$CONTAINER_NAME" -- coverage html
kubectl cp "${CONTAINER_NAME}:/tmp/htmlcov" "$(pwd)/htmlcov/"

if [[ "$CI" = "" ]]; then
    python -m webbrowser -t htmlcov/index.html
fi
