# Original Idea
I want to be able to create an ingress that automatically register a DNS record to one of my standards VS in a LB
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

# Development
By default the operator tries to load the in-cluster credentials (service account usage).
If you're running on local for development, set `MODE` to `DEV` and it will use kubeconfig (~/.kube/config or KUBECONFIG)
```bash
┌──────────────────────────>
│nsupdate-operator/src on  main via 🐍 v3.12.3 (nsupdate-operator) took 4s 
└──➜  KEY="myPLAINkey" MODE=DEV kopf run controller.py
```
