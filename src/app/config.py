#TODO maybe this should be written in a class way?
# so far, allows me to read/prepare values to be used later

import logging
import os
import yaml
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from kubernetes.dynamic import DynamicClient

global zones, standards, master

configmap_name = os.environ.get('configmap','nsupdate-operator-config')


# For development use kubeconfig, otherwise the service account of the pod
config.load_incluster_config() if os.environ.get('MODE','none') != 'DEV' else config.load_kube_config()

try:
    ##TODO validate config
    # DNS Master configuration can be overritten by env vars or something, righ now I will just do for the secret
    dyn_client = DynamicClient(client.ApiClient())
    configmap = dyn_client.resources.get(kind="ConfigMap")
    namespace = os.environ.get('namespace','nsupdate-operator')
    configuration = configmap.get(name=configmap_name,namespace=namespace)
    zones = yaml.safe_load(str(configuration.data["zones"]))
    standards = yaml.safe_load(str(configuration.data["standards"]))
    master = os.environ.get('master',yaml.safe_load(str(configuration.data["master"])))
    logging.info(f"Configuration loaded from {configmap_name} configmap, env vars may still override these values.")
except ApiException as e:
    if e.status == 404:
        logging.info(f"ConfigMap for configuration named {configmap_name} not found. ")
        logging.info(f"We will continue with default configuration")
        zones = ["internal"]
        standards = []
        master = yaml.safe_load("""
            server: "127.0.0.1"
            signer: "root"
            key: "VW5hdXRoZW50aWNhdGVkCg=="
            port: 53
            algorithm: "hmac-sha256"
            timeout: 5
            owner: "someone"
        """   
        )
    else:
        # Log any other errors
        logging.error(
            f"Error handling configuration {configmap_name}: {e.reason} - {e.body}"
        )
except:
    logging.error(f"Fatal error handling configuration")
    exit
    