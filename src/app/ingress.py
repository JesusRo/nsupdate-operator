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
        current_spec = dnsr.get(name=resource_name, namespace=namespace)
        logger.info(f"DNSRecord {resource_name} exists. Checking for updates...")

        # Check if an update is needed
        desired_spec_values = desired_spec["spec"]

        if (
            current_spec.get("record") == desired_spec_values["record"]
            and current_spec.get("type") == desired_spec_values["type"]
            and current_spec.get("target") == desired_spec_values["target"]
        ):
            logger.info(f"DNSRecord {resource_name} is up-to-date.")
            return True

        # Update DNSRecord
        logger.info(f"DNSRecord {resource_name} requires an update.")
        dnsr.patch(
            name=resource_name,
            namespace=namespace,
            body={"spec": desired_spec_values},
            content_type="application/merge-patch+json",
        )
        logger.info(f"DNSRecord {resource_name} updated.")
        return True

    except ApiException as e:
        if e.status == 404:
            # Create DNSRecord if it does not exist
            logger.info(f"DNSRecord {resource_name} not found. Creating one...")
            try:
                dnsr.create(
                    body=desired_spec,
                    namespace=namespace,
                    content_type="application/json",
                )
                logger.info(f"DNSRecord {resource_name} created.")
                return True
            except Exception as create_error:
                raise kopf.TemporaryError(
                    f"Error creating DNSRecord {resource_name}: {create_error}",
                    delay=10,
                )
        else:
            # Handle other API exceptions
            logger.error(f"Error handling DNSRecord {resource_name}: {e.reason} - {e.body}")
            raise kopf.TemporaryError(f"Error handling DNSRecord {resource_name}: {e.reason} - {e.body}",delay=10)
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

    # Find standard set from configuration
    target, record_type = next(
        ((standard["target"], standard["type"]) for standard in standards 
         if standard["key"] == ingress.annotations.get("nsupdate-operator")),
        (None, None)
    )

    if not target or not record_type:
        raise kopf.PermanentError(f"No valid standards found for {ingress.metadata.name} ingress")

    # Process DNSRecords for each host in the ingress rules
    ingress_namespace = ingress.metadata.namespace
    ingress_name = ingress.metadata.name

    for rule in ingress.spec.rules:
        resource_name = f"{ingress_name}--{rule.host}"
        desired_dnsr = create_dns_record_spec(
            resource_name,
            ingress_namespace,
            rule.host,
            target,
            record_type
        )
        kopf.adopt(desired_dnsr)
        logger.info(f"Processing DNSRecord: {resource_name}")
        await sync_dns_record(dnsr, resource_name, ingress_namespace, desired_dnsr, logger)
