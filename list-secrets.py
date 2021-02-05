#!/usr/bin/env python3

import logging
import os
import re
import sys
import yaml


JOBS_DIR = '/home/stevekuznetsov/code/openshift/release/src/github.com/openshift/release/ci-operator/jobs'
CONFIG_DIR = '/home/stevekuznetsov/code/openshift/release/src/github.com/openshift/release/ci-operator/config'
BOOTSTRAP_CONFIG = '/home/stevekuznetsov/code/openshift/release/src/github.com/openshift/release/core-services/ci-secret-bootstrap/_config.yaml'
RAW_CACHE = '/tmp/cache.yaml'

def main():
    with open(RAW_CACHE) as f:
        secretsByNamespace = yaml.load(f, Loader=yaml.SafeLoader)

    if secretsByNamespace == None:
        secretsByNamespace = {}
        for root, _, files in os.walk(JOBS_DIR):
            for filename in files:
                if not filename.endswith('.yaml'):
                    continue
                path = os.path.join(root, filename)
                with open(path) as f:
                    data = yaml.load(f, Loader=yaml.SafeLoader)
                
                ns = "ci"
                if ns not in secretsByNamespace:
                    secretsByNamespace[ns] = set()
                secretsByNamespace[ns].update(secrets(data))

        for root, _, files in os.walk(CONFIG_DIR):
            for filename in files:
                if not filename.endswith('.yaml'):
                    continue
                path = os.path.join(root, filename)
                with open(path) as f:
                    data = yaml.load(f, Loader=yaml.SafeLoader)
                
                ns = "test-credentials"
                if ns not in secretsByNamespace:
                    secretsByNamespace[ns] = set()
                secretsByNamespace[ns].update(credentials(data.get("tests", [])))

        with open(RAW_CACHE,"w") as f:
            yaml.dump(secretsByNamespace, f)

    with open(BOOTSTRAP_CONFIG) as f:
        bootstrapConfig = yaml.load(f, Loader=yaml.SafeLoader)

    bitwardenAttachmentsByItem = {}
    for namespace in secretsByNamespace:
        for secret in secretsByNamespace[namespace]:
            fromBitwarden = False
            for item in bootstrapConfig["secret_configs"]:
                for target in item["to"]:
                    if target["name"] == secret and target["namespace"] == namespace:
                        fromBitwarden = True
                        for field in item["from"]:
                            source = item["from"][field]
                            if "dockerconfigJSON" in source:
                                for auth in source["dockerconfigJSON"]:
                                    bw_item = auth["bw_item"]
                                    bw_attachment = auth["auth_bw_attachment"]
                                    if bw_item not in bitwardenAttachmentsByItem:
                                        bitwardenAttachmentsByItem[bw_item] = set()
                                    bitwardenAttachmentsByItem[bw_item].add(bw_attachment)
                            if "bw_item" in source:
                                if "field" in source:
                                    bw_attachment = source["field"]
                                if "attachment" in source:
                                    bw_attachment = source["attachment"]
                                if "attribute" in source:
                                    bw_attachment = source["attribute"]
                                bw_item = source["bw_item"]
                                if bw_item not in bitwardenAttachmentsByItem:
                                    bitwardenAttachmentsByItem[bw_item] = set()
                                bitwardenAttachmentsByItem[bw_item].add(bw_attachment)
            if not fromBitwarden:
                print("{},{}".format(namespace,secret))

    for item in bitwardenAttachmentsByItem:
        first = True
        for attachment in bitwardenAttachmentsByItem[item]:
            if first:
                print("{},{}".format(item,attachment))
                first = False
            else:
                print(",{}".format(attachment))



def secrets(data):
    secrets = set()
    for job_type in data:
        if job_type == "periodics":
            for job in data[job_type]:
                if job.get("agent", "") != "kubernetes":
                    continue
                if job.get("decoration_config",{}).get("gcs_configuration",{}).get("bucket","origin-ci-test") != "origin-ci-test":
                    continue
                secrets.update(secretsForSpec(job["spec"]))
            continue

        for repo in data[job_type]:
            for job in data[job_type][repo]:
                if job.get("agent", "") != "kubernetes":
                    continue
                if job.get("decoration_config",{}).get("gcs_configuration",{}).get("bucket","origin-ci-test") != "origin-ci-test":
                    continue
                secrets.update(secretsForSpec(job["spec"]))
    return secrets

def secretsForSpec(spec):
    secrets = set()
    runsCiOperator = False
    for container in spec.get("containers", []):
        if "ci-operator" in container.get("image"):
            runsCiOperator = True
    if not runsCiOperator:
        return secrets
    for volume in spec.get("volumes", []):
        if "secret" in volume:
            secrets.add(volume["secret"]["secretName"])
    return secrets

def credentials(tests):
    secrets = set()
    for test in tests:
        for step in test.get("steps",{}).get("test",[]):
            for credential in step.get("credentials",[]):
                secrets.add(credential["name"])
    return secrets


main()