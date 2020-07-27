#!/bin/bash

set -e

kubectl delete -f kubernetes/
kubectl create -f kubernetes/
