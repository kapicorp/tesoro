# Tesoro
Kapitan Secrets Controller for Kubernetes


Tesoro allows you to seamleslsly apply Kapitan secrets & refs in compiled Kubernetes manifests. As it runs in the cluster,
it will be able to reveal embedded kapitan secrets & refs in manifests when applied.

## Example

Say you have this compiled kapitan project:
```
compiled/my-target/manifests
├── my-deployment.yml
└── my-secret.yml
...
```

And you have a kapitan secret in `my-secret.yml`:
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: my-secret
type: Opaque
stringData:
  secret_sauce: ?{gkms:my/secret1:deadbeef}
```

All you have to do is compile secrets as embedded refs:
```shell
$ kapitan compile --embed-refs
```

...and you will notice that your kapitan secret in `my-secret.yml` now looks like:
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

How do I know my secrets and refs revealed succesfully? You would see the following:
```shell
$ kubectl apply -f compiled/my-target/manifests/my-secret.yml
Error from server: error when creating "compiled/my-target/manifests/my-secret.yml": admission webhook "tesoro-admission-controller.tesoro.svc" denied the request: Kapitan reveal failed
```


