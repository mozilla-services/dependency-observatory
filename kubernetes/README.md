WARNING: It's possible for these files to become out of date, as we
don't expect contributors to check these files still work with the
changes they make to the code.

## Running with Kubernetes (k8s)

Running the Dependency Observatory API, worker, and PostgreSQL in a
Kubernetes cluster with minikube:

1. Run `minikube start` (on Linux use `--driver=docker`) to start a local k8s cluster (`minikube stop` to stop it):

```console
$ minikube start
😄  minikube v1.10.1 on Ubuntu 18.04
✨  Automatically selected the docker driver
🎉  minikube 1.11.0 is available! Download it: https://github.com/kubernetes/minikube/releases/tag/v1.11.0
💡  To disable this notice, run: 'minikube config set WantUpdateNotification false'

👍  Starting control plane node minikube in cluster minikube
🔥  Creating docker container (CPUs=2, Memory=3900MB) ...
🐳  Preparing Kubernetes v1.18.2 on Docker 19.03.2 ...
    ▪ kubeadm.pod-network-cidr=10.244.0.0/16
🔎  Verifying Kubernetes components...
🌟  Enabled addons: default-storageclass, storage-provisioner
🏄  Done! kubectl is now configured to use "minikube"
```

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

1. To update images on the k8s cluster (requires linux and minikube running with the docker driver) run the `util/build_and_redeploy_image.sh` script which runs:

```console
$ eval $(minikube -p minikube docker-env) # use the docker on the minikube image (NB: docker-compose won't work)
$ docker build -t mozilla/dependency-observatory:latest .
$ kubectl set image deployments.app/api dependency-observatory-api=mozilla/dependency-observatory:latest
$ kubectl set image deployments.app/worker dependency-observatory-worker=mozilla/dependency-observatory:latest
$ kubectl rollout restart deployment api worker
$ kubectl rollout status deployment api  # to wait for the rollout to complete
```

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
