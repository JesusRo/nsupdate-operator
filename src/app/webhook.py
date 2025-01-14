##TODO learn a bit to avoid this mess
import kopf
from kubernetes.dynamic import DynamicClient
import kubernetes.client

# Constants
CDR="DNSRecord"

# Validating Admission Webhook
@kopf.on.validate(CDR, operations=["CREATE", "UPDATE"], persistent=True)
async def uniquerecord(spec, **_):
    dyn_client = DynamicClient(kubernetes.client.ApiClient())
    all_dnsr = dyn_client.resources.get(kind=CDR).get()
    for dnsr in all_dnsr.attributes.items:
        if (dnsr.spec.record.rstrip(".") == spec.get("record").rstrip(".")) and (spec._src.get("metadata")["name"] != dnsr.get("metadata")["name"]):
            raise kopf.AdmissionError(f"Record must be unique. This record {spec.get('record')} is already being managed by {dnsr.metadata.namespace}/{dnsr.metadata.name}.", code=409)