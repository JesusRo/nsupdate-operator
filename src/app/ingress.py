##TODO a lot of things
# Manage exceptions and logging also pending

# This only watchs for annotated ingresses and create corresponding dnsr resources

import kopf
import kubernetes.client
from kubernetes.client.rest import ApiException
from kubernetes.dynamic import DynamicClient
from kr8s.asyncio.objects import Ingress
from config import standards

# Constants
DNS_RECORD_API_VERSION = "stable.devopstools/v1"
DNS_RECORD_KIND = "DNSRecord"

# Functions 
def create_dns_record_spec(resource_name, namespace, host, target, type):

    return {
        "apiVersion": DNS_RECORD_API_VERSION,
        "kind": DNS_RECORD_KIND,
        "metadata": {
            "name": resource_name,
            "namespace": namespace,
        },
        "spec": {
            "record": host,
            "type": type,
            "target": target,
        },
    }


async def sync_dns_record(dnsr, resource_name, namespace, desired_spec, logger):

    try:
        # Check if the DNSRecord exists
        existing_dnsr = dnsr.get(name=resource_name, namespace=namespace)
        logger.info(f"DNSRecord {resource_name} exists. Checking for updates...")

        # Check if the DNSRecord is up-to-date
        if (
            existing_dnsr.spec.get("record") == desired_spec["spec"]["record"]
            and existing_dnsr.spec.get("type") == desired_spec["spec"]["type"]
            and existing_dnsr.spec.get("target") == desired_spec["spec"]["target"]
        ):
            logger.info(f"DNSRecord {resource_name} is up-to-date.")
        else:
            # Update the DNSRecord if necessary
            logger.info(f"DNSRecord {resource_name} requires an update.")
            patch = {"spec": desired_spec["spec"]}
            dnsr.patch(
                name=resource_name,
                namespace=namespace,
                body=patch,
                content_type="application/merge-patch+json",
            )
            logger.info(f"DNSRecord {resource_name} updated.")
        return
    except ApiException as e:
        if e.status == 404:
            # Create the DNSRecord if it does not exist
            logger.info(f"DNSRecord {resource_name} not found. Creating...")
            try:
                dnsr.create(
                    body=desired_spec,
                    namespace=namespace,
                    content_type="application/json",
                )
                logger.info(f"DNSRecord {resource_name} created.")
            except Exception as e:
                raise kopf.TemporaryError(f"Error creating DNSRecord {resource_name}: {e}", delay=10)
        else:
            # Log any other errors
            logger.error(
                f"Error handling DNSRecord {resource_name}: {e.reason} - {e.body}"
                
            )
            raise kopf.TemporaryError(f"Error handling DNSRecord {resource_name}: {e.reason} - {e.body}", delay=10)
    return False


# Handle deletion of an Ingress resource
@kopf.on.delete(kind="Ingress", annotations={f"nsupdate-operator": kopf.PRESENT})
async def ingress_deleted(body, logger, **kwargs):
    logger.info(f"Ingress {body['metadata']['name']} deleted. Child DNSRecords will be deleted")
    # Child records are deleted thanks to the kopf adoption


# Handle creation, update, and resume of an annotated Ingress resource
@kopf.on.create(kind="Ingress", annotations={f"nsupdate-operator": kopf.PRESENT})
@kopf.on.update(kind="Ingress", annotations={f"nsupdate-operator": kopf.PRESENT})
@kopf.on.resume(kind="Ingress", annotations={f"nsupdate-operator": kopf.PRESENT})
async def ingress_matched(body, logger, **kwargs):

    ingress = await Ingress(body)
    dyn_client = DynamicClient(kubernetes.client.ApiClient())
    dnsr = dyn_client.resources.get(api_version=DNS_RECORD_API_VERSION, kind=DNS_RECORD_KIND)

    target=""
    record_type=""
    for standard in standards:
        if standard["key"] == ingress.annotations[f"nsupdate-operator"]:
            target=standard["target"] 
            record_type=standard["type"] 

    if target == "" or record_type=="":
        raise kopf.PermanentError(f"No standard founds for {ingress.metadata.name} ingress")
        return
    
    for rule in ingress.spec.rules:
        resource_name = f"{ingress.metadata.name}--{rule.host}"
        desired_dnsr = create_dns_record_spec(resource_name, ingress.metadata.namespace, rule.host, target, record_type)
        kopf.adopt(desired_dnsr)
        logger.info(f"Processing DNSRecord: {resource_name}")
        await sync_dns_record(dnsr, resource_name, ingress.metadata.namespace, desired_dnsr, logger)
