WARNING: It's possible for these files to become out of date, as we
don't expect contributors to check these files still work with the
changes they make to the code.

## Running with Kubernetes (k8s)

### Requirements

1. [docker](https://docs.docker.com/get-docker/)
1. [minikube](https://kubernetes.io/docs/tasks/tools/install-minikube/)
1. a GCP account or access to a GCP pubsub account (NB: an emulator exists, but we haven't tested against it)
1. If you also want to use [falco](https://falco.org/), install:

  * [virtualbox 5.2+](https://www.virtualbox.org/wiki/Downloads) (per [the minikube virtualbox driver docs](https://minikube.sigs.k8s.io/docs/drivers/virtualbox/))
  * [helm](https://helm.sh/docs/intro/install/#from-apt-debianubuntu)

### Setup

Running the Dependency Observatory API, worker, and PostgreSQL in a
Kubernetes cluster with minikube:

1. Run `make minikube-start` to start a local k8s cluster (`make minikube-stop-delete` to stop and remove it):

1. Create a kubernetes secret with GCP Service Account key for the `dev-local`
Service Account in the depobs-nonprod project.

```
kubectl create secret generic dev-local-service-account --from-file=key.json=<path/to/KEYFILE.json>
```

1. Change the `GCP_PROJECT_ID` from `replaceme` in the worker deployment

1. Set unique values for `JOB_STATUS_PUBSUB_TOPIC` and
   `JOB_STATUS_PUBSUB_SUBSCRIPTION` and run `gcloud pubsub topics
   create $JOB_STATUS_PUBSUB_TOPIC` and `gcloud pubsub subscriptions
   create $JOB_STATUS_PUBSUB_SUBSCRIPTION` with the values.

1. From the project root, run `kubectl create -f kubernetes/` to start DO (use `kubectl delete -f kubernetes/` to remote it):

```console
$ kubectl create -f kubernetes/
serviceaccount/job-runner created
role.rbac.authorization.k8s.io/job-admin created
rolebinding.rbac.authorization.k8s.io/job-runners-are-job-admins created
deployment.apps/api created
service/api created
deployment.apps/db created
service/db created
deployment.apps/worker created
$
$ kubectl get all # check things are running
NAME                          READY   STATUS        RESTARTS   AGE
pod/api-556fc8c577-jbwpm      1/1     Running       0          14s
pod/db-66c96f6c94-2h8z8       1/1     Running       0          14s
pod/worker-79d8d6d75f-t8tr4   1/1     Running       0          14s

NAME                 TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)    AGE
service/api          ClusterIP   10.100.96.121   <none>        8000/TCP   14s
service/db           ClusterIP   10.104.21.116   <none>        5432/TCP   14s
service/kubernetes   ClusterIP   10.96.0.1       <none>        443/TCP    13m

NAME                     READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/api      1/1     1            1           14s
deployment.apps/db       1/1     1            1           14s
deployment.apps/worker   1/1     1            1           14s

NAME                                DESIRED   CURRENT   READY   AGE
replicaset.apps/api-556fc8c577      1         1         1       14s
replicaset.apps/db-66c96f6c94       1         1         1       14s
replicaset.apps/worker-79d8d6d75f   1         1         1       14s
```

1. To update images on the k8s cluster run `make build-image redeploy`

1. To test CRUD opts on a k8s job run (the api container ID will vary):

```console
$ kubectl exec -i api-556fc8c577-ppr68 -- python < kubernetes/job_crud_test.py
Job created. status='{'active': None,
 'completion_time': None,
 'conditions': None,
 'failed': None,
 'start_time': None,
 'succeeded': None}'
Job updated. status='{'active': 1,
  'completion_time': None,
  'conditions': None,
  'failed': None,
 'start_time': datetime.datetime(2020, 6, 1, 19, 25, 16, tzinfo=tzlocal()),
 'succeeded': None}'
Job deleted. status='{'startTime': '2020-06-01T19:25:16Z', 'active': 1}'
```

1. To access the web API (api container name will vary):

```console
make port-forward
kubectl -n default port-forward svc/api 8000
Forwarding from 127.0.0.1:8000 -> 8000
Forwarding from [::1]:8000 -> 8000
Handling connection for 8000
...
```

1. visit start and report pages:

  * http://localhost:8000/
  * http://localhost:8000/package_report?package_manager=npm&package_name=foo&package_version=2.0.0 (should 404)

1. search for a npm package name andversion to start a scan and score job

#### Falco

1. run `make falco-install` to install falco
