import kopf
import os
import logging

# TODO Implement more meaningful livenessprobe
@kopf.on.probe()
def get_current_timestamp(**kwargs):
    pass

@kopf.on.startup()
async def configure(settings: kopf.OperatorSettings, **_):

    settings.persistence.progress_storage = kopf.AnnotationsProgressStorage(
        prefix="nsupdate-operator"
    )
    settings.persistence.finalizer = "nsupdate-operator/finalizer"

    # Uncomment to limit concurrency for batching operations (if required)
    #settings.batching.worker_limit = 1

    # Disable event posting to Kubernetes to reduce API noise
    settings.posting.enabled = False

    # Now some tricks
    import config
    operator=os.environ.get('operator',"")

    # For development, we run own webhookserver with webhook automanaged by kopf, how to route k8s master to your local is up to you
    if os.environ.get('MODE',"") == "DEV":
        settings.admission.server = kopf.WebhookServer(port=6969)
        settings.admission.managed = 'dnsrecords.stable.devopstools'
        import dnsr
        import ingress
    # On production, first hack, we want diferent containers for each resource observed to avoid interlocks
    # Take a look on the deployment of this in the helm chart
    elif operator=="dnsr":
        settings.admission.server = kopf.WebhookServer(certfile='server.pem', pkeyfile='server-key.pem', port=6969)
        import dnsr
    elif operator=="ingress":
        import ingress 
    else:
        logging.error("'operator' env var is not valid for production, provide 'dnsr' or 'ingress' value")
        exit