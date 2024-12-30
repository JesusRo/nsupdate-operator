# Work in progress
No idea what I'm actually doing so...

## Idea
The objective here is to have something that automatically creates CNAMES for ingresses created
We should have an annotation to flag which ingresses process, and some mapping to use the "standard" entrypoints defined for the cluster

This led to have ingresses with these annotations:
```yaml
  annotations:
    nsupdate-operator: tls-ingress
```
being `tls-ingress` one of the configured "standards" entrypoints
When annotated, it reads all rules and create a crd called dnsr to manage the dns registration

The standards are a list of keys with values for type of record (A/CNAME) and target of the same. This is done via configmap.
In ideal worl, the cluster should have its own soveragne sub-zone, but in real world, it may not
Then, as guardrails, there is a whitelist of zones where dns can be created. Also via configmap
Also, to avoid this takes over existing records managed by other means, adding a TXT entry as a flag of ownership.

And now, we have these dnsr resources, that are managed by this operator to try to create those records or register the error


## Stuffs for later
### Secret template for sealed secrets
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: nsupdate-operator-secret
  namespace: nsupdate-operator-system
stringData:
  KEY: myPLAINpasswordhere
type: Opaque
```

### Webhook development
You need to somehow to make posible kubeapi to call your localhost
```bash
ssh -R 6969:127.0.0.1:6969 k8s-master.environment.devops
```