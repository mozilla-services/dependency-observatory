#!/bin/bash

set -e

# redeploy
kubectl rollout restart deployment api
# kubectl rollout restart deployment worker
kubectl rollout status deployment api
# kubectl rollout status deployment worker
