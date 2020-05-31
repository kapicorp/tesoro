# Tesoro
Kapitan Secrets Controller for Kubernetes


Tesoro allows you to seamleslsly apply Kapitan secrets & refs in compiled manifests. As it runs in the cluster,
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
...
```

