#!/bin/bash

# requires a running api container
CONTAINER_NAME=${CONTAINER_NAME:-$(kubectl get pods -l io.kompose.service=api -o go-template --template '{{range .items}}{{.metadata.name}}{{"\n"}}{{end}}')}

kubectl cp tests/ "${CONTAINER_NAME}:/tmp/"
kubectl exec -it "$CONTAINER_NAME" -- pytest -c /app/setup.cfg /tmp/tests /app/depobs/ "$@"
