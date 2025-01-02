# Work in progress
No idea what I'm actually doing so...

##  Original Idea
I want to be able to create an ingress that automatically register a DNS record to one of my standards VS in a LB in a dynamic dns zone
I want this resource:
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: random-app
spec:
  rules:
  - host: "jromero-ingress.environment.internal"
    http:
      paths:
      - path: /testpath
        pathType: Prefix
        backend:
          service:
            name: test
            port:
              number: 80
  - host: "jromero-ingress.environment.devops"
    http:
      paths:
      - path: /testpath
        pathType: Prefix
        backend:
          service:
            name: test
            port:
              number: 80
```
This should automatically creates a DNS record to an standard entrypoint just adding below annotation to it
```yaml
  annotations:
    nsupdate-operator: http
```
Additionally, I want to be able to register DNS entries on demand.
All this having some kind of guardrails as
- limit DNS zones 
- avoid interfering with entries not managed by this instance operator

## Images
Uploaded to https://hub.docker.com/r/jesusro/nsupdate-operator 

## How to use this as a chart
Simply deploy to your environment
```bash
helm install -f myvalues.yaml nsupdate-operatpr ./charts/nsupdate-operator
```


#### Development
By default the operator tries to load the in-cluster credentials (service account usage).
If you're running on local for development, set `MODE` to `DEV` and it will use kubeconfig (~/.kube/config or KUBECONFIG)
```bash
┌──────────────────────────>
│nsupdate-operator/src on  main via 🐍 v3.12.3 (nsupdate-operator) took 4s 
└──➜  KEY="myPLAINkey" MODE=DEV kopf run controller.py
```
#### Webhook development
You need to somehow make posible kubeapi to call your localhost
```bash
ssh -R 6969:127.0.0.1:6969 k8s-master.environment.devops
```

#### Secret template for sealed secrets
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: nsupdate-operator-secret
  namespace: nsupdate-operator
stringData:
  KEY: myPLAINpasswordhere
type: Opaque
```
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: nsupdate-operator-certs
  namespace: nsupdate-operator
stringData:
  key: |
    -----BEGIN RSA PRIVATE KEY-----
    MIIEpAIBAAKCAQEAv5s+hkZ3uMzxnSs+cq21rLQlkce325VUjiLGbT+fUBXQ6OPJ
    gclfGifzIQ/iSmWUpKiXi2rzCO9XsxtAKztaryYPm7YU66HazUo3JctE5RHhS1oh
    [...]
    [...]
    [...]
    993CFkGCidnkZWdO5B+t6nDm2zMJZKRPkEe0nJ+TDmR5drODjfjWfY/41w/5hyTM
    WCNJ9cpReodB8xl3PBUy7iyTdr6LRj37foAQJaEeVWoM17Dozd5ncg==
    -----END RSA PRIVATE KEY-----
  server: |
    -----BEGIN CERTIFICATE-----
    MIIEBzCCAu+gAwIBAgIUPqgee+GyEYPllI2c6WfdqwTiKmAwDQYJKoZIhvcNAQEL
    BQAwZDENMAsGA1UEBhMETm9uZTENMAsGA1UECBMETm9uZTENMAsGA1UEBxMETm9u
    [...]
    [...]
    [...]
    5edvzLf2esormHLqp/FqttzbqZpwvSECoUMw8HMhUe17tEvxwdQQiJCSS061bAcz
    6l2K0FUDnj03AjuAqgxTjuL84DXCl4Dsyxpu
    -----END CERTIFICATE-----
type: Opaque
```