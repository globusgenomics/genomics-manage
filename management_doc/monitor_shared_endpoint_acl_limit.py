#!/usr/bin/env python
import globus_sdk
import re
import sys

endpoint_id = "e18ffae2-ebb9-11e6-b9d6-22000b9a448b"

#CRED_FILE = "/home/galaxy/.globusgenomics/globus_transfer_cred"

client_id = None
transfer_rt = None
transfer_at = None
expires_at_s = int("1485641163")
"""
with open(CRED_FILE) as f:
    for line in f:
        if line.startswith("client_id:"):
            client_id = re.sub("client_id:","",line,count=1).strip()
        if line.startswith("refresh_token:"):
            transfer_rt = re.sub("refresh_token:","",line,count=1).strip()
        if line.startswith("access_token:"):
            transfer_at = re.sub("access_token:","",line,count=1).strip()
        if line.startswith("expires_at_seconds:"):
            expires_at_s = int(re.sub("expires_at_seconds:","",line,count=1).strip())
"""

client = globus_sdk.NativeAppAuthClient(client_id)

authorizer = globus_sdk.RefreshTokenAuthorizer(
                transfer_rt, client, access_token=transfer_at, expires_at=expires_at_s)

tc = globus_sdk.TransferClient(authorizer=authorizer)

acl_list = tc.endpoint_acl_list(endpoint_id)

acl_num = len(acl_list["DATA"])

to_print = "acl num {0}".format(acl_num)

if acl_num > 800:
    print to_print
    sys.exit(1)
else:
    print to_print
    sys.exit(0)