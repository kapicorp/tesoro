# Tesoro
[Kapitan](https://kapitan.dev) Secrets Webhook for Kubernetes


Tesoro allows you to seamleslsly apply Kapitan [secret refs](https://kapitan.dev/secrets/) in compiled Kubernetes manifests. As it runs in the cluster,
it will be able to reveal embedded kapitan secret refs in manifests when applied.

## Example

Say you have just setup Tesoro and have this compiled kapitan project:
```
compiled/my-target/manifests
├── my-deployment.yml
└── my-secret.yml
...
```

And you have the Tesoro reveal annotation and kapitan secret ref in `my-secret.yml`:
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: my-secret
  annotations:
    kapicorp.com/tesoro: kapitan-reveal-refs
type: Opaque
stringData:
  secret_sauce: ?{gkms:my/secret1:deadbeef}
```

All you have to do is compile with embedded refs:
```shell
$ kapitan compile --embed-refs
```

...and you will notice that your kapitan secret ref in `my-secret.yml` now looks like:
```yaml
...
type: Opaque
stringData:
  secret_sauce: ?{gkms:eyJkYXRhIjogImNtVm1JREVnWkdGMFlRPT0iLCAiZW5jb2RpbmciOiAib3JpZ2luYWwiLCAidHlwZSI6ICJiYXNlNjQifQ==:embedded}}
...
```

This means that your kubernetes manifests and secrets are ready to be applied:
```shell
$ kubectl apply -f compiled/my-target/manifests/my-secret.yml
secret/my-secret configured
```

Why is this a big deal? Because without Tesoro, you'd have to reveal secrets locally when applying:
```shell
$ kapitan refs --reveal -f compiled/my-target/manifests/my-secret.yml | kubectl apply -f -
```

How do I know my secrets refs revealed succesfully? You would see the following:
```shell
$ kubectl apply -f compiled/my-target/manifests/my-secret.yml
Error from server: error when creating "compiled/my-target/manifests/my-secret.yml": admission webhook "tesoro-admission-controller.tesoro.svc" denied the request: Kapitan reveal failed
```
You can also setup Prometheus monitoring for this. See [Monitoring](https://github.com/kapicorp/tesoro/#monitoring)

## Setup
Tesoro is a Kubernetes Admission Controller [Mutating Webhook](https://kubernetes.io/docs/reference/access-authn-authz/admission-controllers/#mutatingadmissionwebhook), which means that you'll need at minimum a Kubernetes v1.13 cluster with [PodSecurityPolicy](https://kubernetes.io/docs/reference/access-authn-authz/admission-controllers/#podsecuritypolicy) support enabled (e.g. in GCP, a cluster created with the `--enable-pod-security-policy` flag)

### Example Kubernetes Config
You'll find the predefined example config in the [k8s/](./k8s) directory. Please make sure you read about setting up Mutating Webhooks [here](https://kubernetes.io/docs/reference/access-authn-authz/extensible-admission-controllers/#configure-admission-webhooks-on-the-fly)!

#### 1 - ClusterRole and ClusterRoleBinding
```shell
$ kubectl apply -f k8s/clusterrole.yaml
$ kubectl apply -f k8s/clusterrolebinding.yaml
```
#### 2 - Pod Security Policy (you will likely need it but this one is relaxed and for example only!)
```shell
$ kubectl apply -f k8s/pod_security_policy.yaml
```
#### 3 - Tesoro Namespace
We will be running the webhook and testing in the `tesoro` namespace
```shell
$ kubectl apply -f k8s/tesoro_namespace.yaml
```

#### 4 - Tesoro Webhook Config & Certs
For convenience, you'll find valid certificates in `tesoro_mutatingwebhook.yaml` and `tesoro_secret.yaml` for testing purposes only.

Security advice: FOR PROD, PLEASE SETUP YOUR OWN.

```shell
$ kubectl -n tesoro apply -f k8s/tesoro_service_account.yaml
$ kubectl -n tesoro apply -f k8s/tesoro_secret.yaml
$ kubectl -n tesoro apply -f k8s/tesoro_service.yaml
$ kubectl -n tesoro apply -f k8s/tesoro_deployment.yaml
```

Verify the tesoro pod is up and running:
```shell
$ kubectl -n tesoro get pods
NAME                                           READY   STATUS    RESTARTS   AGE
tesoro-admission-controller-584b9d87c6-p69bx   1/1     Running   0          1m
```

And finally apply the MutatingWebhookConfiguration:
```shell
$ kubectl -n tesoro apply -f k8s/tesoro_deployment.yaml
```

#### 5 - Try a Kubernetes Manifest with Secret Refs
This manifest with a valid ref, should work:
```shell
$ kubectl -n tesoro apply -f k8s/nginx_deployment.yml
deployment.apps/nginx-deployment created
```


The following manifest with a bogus ref, should fail:
```shell
kubectl -n tesoro apply -f k8s/nginx_deployment_bad.yml
Error from server: error when creating "nginx_deployment_bad.yml": admission webhook "tesoro-admission-controller.tesoro.svc" denied the request: Kapitan reveal failed
```

## Monitoring
Tesoro exposes a Prometheus endpoint (default on port 9095) and the following metrics:

Metric | Description | Type
------------ | ------------- | ------------
tesoro_requests_total | Tesoro total requests | counter
tesoro_requests_failed_total | Tesoro failed requests | counter
kapitan_reveal_requests_total | Kapitan reveal total requests | counter
kapitan_reveal_requests_failed_total | Kapitan reveal failed requests | counter

