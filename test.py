import boto3
from pprint import pprint

client = boto3.client('ec2', region_name='us-east-1')

response = client.describe_volumes(VolumeIds=[])
pprint(response)