##TODO learn a bit to avoid this mess
# Manage exceptions and logging also pending

# Here is where the dirty stuffs happen
# This manages the dnsr crds and actions agains dns master

import kopf
import logging
import dns.update
import dns.query
import dns.tsigkeyring
import dns.resolver
import os
import yaml
import re
from kubernetes.dynamic import DynamicClient
import kubernetes.client
from datetime import datetime
from config import zones, master
from dataclasses import dataclass
import time

# Constants
KEY = os.environ.get('KEY')
SERVER = str(master[f"server"])
ALGORITHM = str(master[f"algorithm"])
KEYRING = dns.tsigkeyring.from_text({master[f"signer"]: KEY})
PORT = int(master[f"port"])
TIMEOUT = int(master[f"timeout"])
CDR="DNSRecord"
OWNMARK=f"nsupdate-operator_{str(master['owner'])}"
TTL=300

class Statuses():
    SYNCED = "Synced"
    PENDING = "Pending"
    ERROR = "Error"
    DELETED = "Deleted"
    PROPAGATION = "Propagation"

class Records():
    A = "A"
    CNAME = "CNAME"
    TXT = "TXT"

@dataclass
class DnsRecord:
    record: str
    target: str = "0.0.0.0"
    record_type: Records = Records.A
    status: Statuses = Statuses.PENDING

    def _starget(self) -> str:
        return self.target.rstrip(".") + "." if self.record_type == Records.CNAME else self.target

    def validate_zone(self) -> bool:
        target_zone = self.record.split(".", 1)[1]
        if target_zone.rstrip(".") not in zones and target_zone.rstrip(".") + "." not in zones:
            return False
        return True

    def validate_target(self) -> bool:
        if self.record_type == Records.CNAME:
            try:
                resolver = dns.resolver.Resolver()
                resolver.nameservers = [SERVER]
                resolver.port = PORT
                resolver.timeout = TIMEOUT
                resolver.resolve(self._starget())
            except Exception as e:
                logging.warning(f"Error resolving {self._starget}: {e}")
                return False
        else:
            pattern = re.compile(r"^((25[0-5]|(2[0-4]|1\d|[1-9]|)\d)(\.(?!$)|$)){4}$")
            return pattern.match(self._starget())
        return True

    def resolve(self, record_type: Records = None, master: bool = True) -> str | bool:
        record_type = record_type or self.record_type
        try:
            resolver = dns.resolver.Resolver()
            if master:
                resolver.nameservers = [SERVER]
                resolver.port = PORT
                resolver.timeout = TIMEOUT
            response = resolver.resolve(self.record.rstrip("."), record_type)
            return str(response[0])
        except Exception as e:
            logging.warning(f"Error resolving {self.record.rstrip(".")}: {e}")
            return False

    def owned(self) -> bool:
        try:
            resolver = dns.resolver.Resolver()
            resolver.nameservers = [SERVER]
            resolver.port = PORT
            resolver.timeout = TIMEOUT
            response = resolver.resolve("owner_"+self.record.rstrip("."), Records.TXT)
            return str(response[0] == OWNMARK)
        except Exception as e:
            logging.warning(f"Error resolving TXT for {self.record.rstrip(".")}: {e}")
            return False

    def synced(self) -> bool:
        return self.resolve() == (False if self.status == Statuses.DELETED else self._starget())

    def propagated(self) -> bool:
        return self.resolve(master=False) == (False if self.status == Statuses.DELETED else self._starget())

    def sync(self) -> bool:
        zone=self.record.split(".", 1)[1]
        host=self.record.replace("."+zone,"")
        target = self._starget()
        update = dns.update.Update(zone, keyring=KEYRING, keyalgorithm=ALGORITHM)

        if self.status == Statuses.DELETED:
            update.delete(host, self.record_type)
            update.delete("owner_"+host, Records.TXT)
        else:
            update.replace(host, TTL, self.record_type, target)
            update.replace("owner_"+host, TTL, Records.TXT, OWNMARK)
        try:
            dns.query.tcp(update, SERVER, port=PORT, timeout=TIMEOUT)
            time.sleep(TIMEOUT)
            return True
        except Exception as e:
            logging.warning(f"Error syncing record {self.record} with target {target}: {e}")
            return False

def update_status(patch, state, error_message=None):
    patch.status.update({
        'state': state,
        'lastUpdated': datetime.now().strftime("%d/%m/%Y, %H:%M:%S"),
        'errorMessage': error_message
    })

@kopf.on.delete(kind=CDR)
async def dnsr_deleted(spec, patch, **kwargs):
    dnsr = DnsRecord(record=spec.get("record"), record_type=spec.get("type"), status=Statuses.DELETED)
    
    if not dnsr.owned():
        update_status(patch, Statuses.DELETED,f"Record {dnsr.record} is not managed by this by this operator")
        return True

    if not dnsr.sync():
        patch.status['errorMessage'] = "Error sending delete request"
        raise kopf.PermanentError(f"Error sending delete request")

    if not dnsr.synced():
        patch.status['errorMessage'] = "Deletion has not been synced yet"
        raise kopf.TemporaryError(f"Error deleting dns record", delay=10)

    if not dnsr.propagated():
        patch.status['errorMessage'] = "Deletion has not been propagated yet"
        raise kopf.TemporaryError(f"Error deleting dns record", delay=10)

@kopf.on.update(kind=CDR)
async def dnsr_updated(old, new, patch, **_):
    update_status(patch, Statuses.PENDING,f"N/A")
    await dnsr_deleted(spec=old["spec"], patch=patch)
    await dnsr_created(spec=new["spec"], patch=patch)

@kopf.on.resume(kind=CDR)
@kopf.on.create(kind=CDR)
async def dnsr_created(spec, patch, **kwargs):
    dnsr = DnsRecord(record=spec.get("record"), record_type=spec.get("type"), target=spec.get("target"))
    update_status(patch, Statuses.PENDING)

    if not dnsr.validate_zone():
        update_status(patch, Statuses.ERROR,f"Record {dnsr.record} doesn't belong to any of the allowed zones: {zones}")
        raise kopf.PermanentError(f"Record doesn't belong to allowed zones")

    if not dnsr.validate_target():
        update_status(patch, Statuses.ERROR,f"Target {dnsr.target} cannot be resolved by master dns")
        raise kopf.PermanentError(f"Target do not exist")

    if dnsr.resolve(Records.CNAME) or dnsr.resolve(Records.A): #Had to check both to ensure "record is free to use"
        if not dnsr.owned():
            update_status(patch, Statuses.ERROR,f"Record {dnsr.record} already exists but it is not managed by this operator")
            raise kopf.PermanentError(f"Record not owned")
        if not dnsr.synced():
            if not dnsr.sync():
                update_status(patch, Statuses.ERROR,f"Error sending creation request")
                raise kopf.PermanentError(f"Error sending creation request")
            raise kopf.TemporaryError(f"Sent resync request")
        else:
            if dnsr.propagated() != True:
                update_status(patch, Statuses.PROPAGATION)
                raise kopf.TemporaryError(f"Record is not propagated yet", delay=10)
            update_status(patch, Statuses.SYNCED,f"N/A")
    else:
        if not dnsr.sync():
            patch.status['errorMessage'] = "Error sending creation request"
            raise kopf.PermanentError(f"Error sending creation request")
        if not dnsr.synced():
            patch.status['errorMessage'] = "Creation has not been performed properly"
            raise kopf.TemporaryError(f"Error creating dns record", delay=10)
        update_status(patch, Statuses.PROPAGATION)
        if not dnsr.propagated():
            raise kopf.TemporaryError(f"Propagation not completed", delay=10)
        update_status(patch, Statuses.SYNCED, f"N/A")


# Validating Admission Webhook
@kopf.on.validate(CDR, operations=["CREATE", "UPDATE"], persistent=True)
async def uniquerecord(spec, **_):
    dyn_client = DynamicClient(kubernetes.client.ApiClient())
    all_dnsr = dyn_client.resources.get(kind=CDR).get()
    for dnsr in all_dnsr.attributes.items:
        if (dnsr.spec.record.rstrip(".") == spec.get("record").rstrip(".")) and (spec._src.get("metadata")["name"] != dnsr.get("metadata")["name"]):
            raise kopf.AdmissionError(f"Record must be unique. This record {spec.get('record')} is already being managed by {dnsr.metadata.namespace}/{dnsr.metadata.name}.", code=409)


# TODO decide if we want to trigguer by timer
# in case something external touched our records