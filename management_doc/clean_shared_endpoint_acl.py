import globus_sdk
import re

endpoint_id = "EP_ID"
CRED_FILE = "/home/galaxy/.globusgenomics/globus_transfer_cred"

client_id = None
transfer_rt = None
transfer_at = None
expires_at_s = None
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

client = globus_sdk.NativeAppAuthClient(client_id)

authorizer = globus_sdk.RefreshTokenAuthorizer(
                transfer_rt, client, access_token=transfer_at, expires_at=expires_at_s)

tc = globus_sdk.TransferClient(authorizer=authorizer)

acl_list = tc.endpoint_acl_list(endpoint_id)
print acl_list
for item in acl_list:
    if item['role_type'] != 'administrator':
        tc.delete_endpoint_acl_rule(endpoint_id, item["id"])
    #if item["path"] == "/xiao2.243859313@eupathdb.org/":
    #    print item
        #print "deleting"
        #tc.delete_endpoint_acl_rule(endpoint_id, item["id"])

print len(acl_list["DATA"])