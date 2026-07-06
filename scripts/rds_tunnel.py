#!/usr/bin/env python3
"""Start SSM port-forwarding session to RDS via bastion."""

import argparse
import subprocess

import boto3


def get_bastion_instance_id(name_prefix: str, region: str) -> str:
    ec2 = boto3.client("ec2", region_name=region)
    resp = ec2.describe_instances(
        Filters=[
            {"Name": "tag:Name", "Values": [f"{name_prefix}-bastion"]},
            {"Name": "instance-state-name", "Values": ["running"]},
        ]
    )
    instances = [i for r in resp["Reservations"] for i in r["Instances"]]
    if not instances:
        raise RuntimeError(f"No running bastion found for {name_prefix}")
    return instances[0]["InstanceId"]


def get_rds_endpoint(name_prefix: str, region: str) -> str:
    rds = boto3.client("rds", region_name=region)
    resp = rds.describe_db_instances(DBInstanceIdentifier=name_prefix)
    return resp["DBInstances"][0]["Endpoint"]["Address"]


def main() -> None:
    parser = argparse.ArgumentParser(description="SSM port-forwarding to RDS via bastion")
    parser.add_argument("--env", default="test", help="Environment (default: test)")
    parser.add_argument("--port", default="5432", help="Local port (default: 5432)")
    parser.add_argument("--region", default="us-west-2", help="AWS region (default: us-west-2)")
    args = parser.parse_args()

    name_prefix = f"aily-{args.env}"

    print(f"Environment : {args.env}")
    print(f"Region      : {args.region}")
    instance_id = get_bastion_instance_id(name_prefix, args.region)
    print(f"Bastion     : {instance_id}")
    endpoint = get_rds_endpoint(name_prefix, args.region)
    print(f"RDS         : {endpoint}")
    print(f"Local port  : {args.port}")
    print("\nConnecting... (Ctrl+C to stop)")
    print(f'  psql "postgresql://<username>:<password>@127.0.0.1:{args.port}/mlflow?sslmode=require"')

    subprocess.run(
        [
            "aws", "ssm", "start-session",
            "--region", args.region,
            "--target", instance_id,
            "--document-name", "AWS-StartPortForwardingSessionToRemoteHost",
            "--parameters", f"host={endpoint},portNumber=5432,localPortNumber={args.port}",
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
