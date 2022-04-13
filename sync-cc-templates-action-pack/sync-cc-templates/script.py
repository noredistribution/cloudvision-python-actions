# Copyright (c) 2022 Arista Networks, Inc.
# Use of this source code is governed by the Apache License 2.0
# that can be found in the COPYING file.

from cloudvision.Connector.grpc_client import GRPCClient, create_query, create_notification
from cloudvision.Connector.codec.custom_types import FrozenDict
from cloudvision.Connector.codec import Wildcard, Path
from google.protobuf.timestamp_pb2 import Timestamp
import requests
import json
import ssl


def get_client(apiserverAddr, token=None, certs=None, key=None, ca=None):
    ''' Returns the gRPC client used for authentication'''
    return GRPCClient(apiserverAddr, token=token, key=key, ca=ca, certs=certs)


def get(client, dataset, pathElts):
    ''' Returns a query on a path element'''
    result = {}
    query = [
        create_query([(pathElts, [])], dataset)
    ]

    for batch in client.get(query):
        for notif in batch["notifications"]:
            result.update(notif["updates"])
    return result


def getSwitchesInfo(client):
    pathElts = [
        "DatasetInfo",
        "Devices"
    ]
    dataset = "analytics"
    return get(client, dataset, pathElts)


def getCcPath(client):
    ''' Returns all turbine config pointers'''
    pathElts = [
        "changecontrol"
    ]
    dataset = "cvp"
    return unfreeze(get(client, dataset, pathElts))


def getCcPathVersions(client, cc_type):
    ''' Returns all turbine config pointers'''
    pathElts = [
        "changecontrol",
        cc_type
    ]
    dataset = "cvp"
    return unfreeze(get(client, dataset, pathElts))


def getCcTemplates(client):
    ''' Returns all turbine config pointers'''
    pathElts = [
        "changecontrol",
        "template",
        "v1",
        Wildcard()
    ]
    dataset = "cvp"
    return unfreeze(get(client, dataset, pathElts))


def getCcActionBundles(client):
    ''' Returns all turbine config pointers'''
    pathElts = [
        "changecontrol",
        "actionBundle",
        "v1",
        Wildcard()
    ]
    dataset = "cvp"
    return unfreeze(get(client, dataset, pathElts))


def unfreeze(o):
    ''' Used to unfreeze Frozen dictionaries'''
    if isinstance(o, (dict, FrozenDict)):
        return dict({k: unfreeze(v) for k, v in o.items()})

    if isinstance(o, (str)):
        return o

    try:
        return [unfreeze(i) for i in o]
    except TypeError:
        pass

    return o


def publish(client, dataset, pathElts, data={}):
    ''' Publish function used to update specific paths in the database'''
    ts = Timestamp()
    ts.GetCurrentTime()

    # Boilerplate values for dtype, sync, and compare
    dtype = "device"
    sync = True
    compare = None

    updates= [(key, value) for key, value in data.items()]

    notifs = [create_notification(ts, pathElts, updates=updates)]

    client.publish(dtype=dtype, dId=dataset, sync=sync, compare=compare, notifs=notifs)
    return 0


def backupConfig(serverType, data):
    ''' Saves data in a json file'''
    filename = "/tmp/backup" + str(serverType) + ".json"
    with open(filename, 'w') as json_file:
        json.dump(data, json_file, indent=4)


def login(url_prefix, username, password):
    connect_timeout = 10
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    session = requests.Session()
    authdata = {"userId": username, "password": password}
    response = session.post(
        "https://" + url_prefix + "/web/login/authenticate.do",
        data=json.dumps(authdata),
        headers=headers,
        timeout=connect_timeout,
        verify=False,
    )
    if "sessionId" not in response.json():
        raise UserWarning("The provided credentials are incorrect.")
    else:
        token = response.json()["sessionId"]
        sslcert = ssl.get_server_certificate((url_prefix, 8443))
        return [token, sslcert]


# Create client for remote CVP server
dstUser: str = ctx.changeControl.args.get("dstUser")
dstPassword: str = ctx.changeControl.args.get("dstPassword")
dst: str = ctx.changeControl.args.get("dst")

token = "/tmp/token.txt"
ca = "/tmp/cert.crt"
creds = login(dst.split(":")[0], dstUser, dstPassword)
with open(token, "w") as f:
    f.write(creds[0])
    f.close()
with open(ca, "w") as f:
    f.write(creds[1])
    f.close()
clientDst = get_client(dst, certs=None, key=None, token=token, ca=ca)

# create client for local CVP server
clientSrc: GRPCClient = ctx.getCvClient()

# fetch local and remote CC templates and actionBundles
source_templates = getCcTemplates(clientSrc)
dest_templates = getCcTemplates(clientDst)
source_action_bundles = getCcActionBundles(clientSrc)
dest_action_bundles = getCcActionBundles(clientDst)

# backup CC templates and actionBundles
ctx.alog("Backing up CC templates and actionBundles to /tmp directory...")
backupConfig('source-cvp-tmpl', source_templates)
backupConfig('dest-cvp-tmpl', dest_templates)
backupConfig('source-cvp-ab', source_action_bundles)
backupConfig('dest-cvp-ab', dest_action_bundles)
ctx.alog("Backup has completed.")

# Check if the pointers already exist
# If there were no templates/actionBundles created previously we have to populate these first
dataset = 'cvp'
pList = ['template', 'actionBundle']
cc_ptrs = getCcPath(clientDst)

ctx.alog("Checking if 'template' and 'actionBundle' pointers exist in cvp:/changecontrol/ and creating if it doesn't.")

for ptr in pList:
    cc_versions = getCcPathVersions(clientDst, ptr)
    if ptr not in list(cc_ptrs.keys()):
        pathElts = ["changecontrol"]
        ptrData = {ptr: Path(keys=["changecontrol", ptr])}
        publish(clientDst, dataset, pathElts, ptrData)
    if cc_versions == {}:
        pathElts = ["changecontrol", ptr]
        ptrData = {"v1": Path(keys=["changecontrol", ptr, "v1"])}
        publish(clientDst, dataset, pathElts, ptrData)

# Publish the CC templates to the target cluster
ctx.alog("Publishing the CC templates to the target cluster...")
for tmpl_key in source_templates:
    pathElts = ["changecontrol", "template", "v1", tmpl_key]
    update = {tmpl_key: source_templates[tmpl_key]}
    publish(clientDst, dataset, pathElts, update)
    ptrData = {tmpl_key: Path(keys=["changecontrol", "template", "v1", tmpl_key])}
    publish(clientDst, dataset, pathElts[:-1], ptrData)
ctx.alog("CC templates have been successfully published")

# Publish the CC Action Bundles to the target cluster
ctx.alog("Publishing the CC Action Bundles to the target cluster...")
for ab_key in source_action_bundles:
    pathElts = ["changecontrol", "actionBundle", "v1", ab_key]
    update = {ab_key: source_action_bundles[ab_key]}
    publish(clientDst, dataset, pathElts, update)
    ptrData = {ab_key: Path(keys=["changecontrol", "actionBundle", "v1", ab_key])}
    publish(clientDst, dataset, pathElts[:-1], ptrData)
ctx.alog("CC action bundles have been successfully published")
