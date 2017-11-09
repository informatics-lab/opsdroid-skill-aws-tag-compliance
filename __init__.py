import logging
import random

import aiobotocore

from opsdroid.matchers import match_crontab, match_regex


_LOGGER = logging.getLogger(__name__)


################################################################################
# Helper functions                                                             #
################################################################################


async def get_instances(aws_access_key_id, aws_secret_access_key, regions):
    """Gets a list of all instances on AWS for a list of regions."""
    instances = []

    session = aiobotocore.get_session()
    for region in regions:
        async with session.create_client("ec2",
                                         aws_access_key_id=aws_access_key_id,
                                         aws_secret_access_key=aws_secret_access_key,
                                         region_name=region) as ec2:
            region_instances = await ec2.describe_instances()

            for reservation in region_instances["Reservations"]:
                for instance in reservation["Instances"]:
                    instance["region"] = region
                    instances.append(instance)

    return instances


async def tag_instances(aws_access_key_id, aws_secret_access_key, instances, tags):
    """Add a set of tags to a set of instances."""
    session = aiobotocore.get_session()
    for instance in instances:
        async with session.create_client("ec2",
                                         aws_access_key_id=aws_access_key_id,
                                         aws_secret_access_key=aws_secret_access_key,
                                         region_name=instance["region"]) as ec2:
            await ec2.create_tags(
                Resources=[instance["InstanceId"]],
                Tags=tags
            )


async def get_buckets(aws_access_key_id, aws_secret_access_key, regions):
    """Gets a list of all buckets on AWS for a list of regions."""
    buckets = []

    session = aiobotocore.get_session()
    for region in regions:
        async with session.create_client("s3",
                                         aws_access_key_id=aws_access_key_id,
                                         aws_secret_access_key=aws_secret_access_key,
                                         region_name=region) as s3:
            region_buckets = await s3.list_buckets()

            for bucket in region_buckets["Buckets"]:
                bucket["region"] = region
                buckets.append(bucket)

    return buckets


async def tag_buckets(aws_access_key_id, aws_secret_access_key, buckets, tags):
    """Add a set of tags to a set of buckets."""
    session = aiobotocore.get_session()
    for bucket in buckets:
        async with session.create_client("s3",
                                         aws_access_key_id=aws_access_key_id,
                                         aws_secret_access_key=aws_secret_access_key,
                                         region_name=bucket["region"]) as s3:

            bucket_tags = tags + await parse_tags({"Name": bucket["Name"]})
            await s3.put_bucket_tagging(
                Bucket = bucket["Name"],
                Tagging = {'TagSet': bucket_tags}
            )


async def get_volumes(aws_access_key_id, aws_secret_access_key, regions):
    """Gets a list of all volumes on AWS for a list of regions."""
    volumes = []
    session = aiobotocore.get_session()
    for region in regions:
        async with session.create_client("ec2",
                                         aws_access_key_id=aws_access_key_id,
                                         aws_secret_access_key=aws_secret_access_key,
                                         region_name=region) as ec2:
            region_volumes = await ec2.describe_volumes()

            for volume in region_volumes["Volumes"]:
                volume["region"] = region
                volumes.append(volume)

    return volumes


async def tag_volumes(aws_access_key_id, aws_secret_access_key, volumes, tags):
    """Add a set of tags to a set of instances."""
    session = aiobotocore.get_session()
    for volume in volumes:
        async with session.create_client("ec2",
                                         aws_access_key_id=aws_access_key_id,
                                         aws_secret_access_key=aws_secret_access_key,
                                         region_name=volume["region"]) as ec2:
            volume_tags = tags
            if "Name" not in [tag["Key"] for tag in volume["Tags"]] and len(volume["Attachments"]) == 1:
                volume_tags = volume_tags + await parse_tags({"Name": volume["Attachments"][0]["InstanceId"]})
            await ec2.create_tags(
                Resources=[volume["VolumeId"]],
                Tags=volume_tags
            )


async def get_elbs(aws_access_key_id, aws_secret_access_key, regions):
    """Gets a list of all ELBs on AWS for a list of regions."""
    elbs = []

    session = aiobotocore.get_session()
    for region in regions:
        async with session.create_client("elb",
                                         aws_access_key_id=aws_access_key_id,
                                         aws_secret_access_key=aws_secret_access_key,
                                         region_name=region) as elbv1:
            region_elb = await elbv1.describe_load_balancers()

            for elb in region_elb["LoadBalancerDescriptions"]:
                elb["region"] = region
                elbs.append(elb)

    return elbs


async def tag_elbs(aws_access_key_id, aws_secret_access_key, elbs, tags):
    """Add a set of tags to a set of ELBs."""
    session = aiobotocore.get_session()
    for elb in elbs:
        async with session.create_client("elb",
                                         aws_access_key_id=aws_access_key_id,
                                         aws_secret_access_key=aws_secret_access_key,
                                         region_name=elb["region"]) as elbv1:

            elb_tags = tags + await parse_tags({"Name": elb["LoadBalancerName"]})
            await elbv1.add_tags(
                LoadBalancerNames = [elb["LoadBalancerName"]],
                Tags = elb_tags
            )

async def get_lambdas(aws_access_key_id, aws_secret_access_key, regions):
    """Gets a list of all lambda functions on AWS for a list of regions."""
    λs = []

    session = aiobotocore.get_session()
    for region in regions:
        async with session.create_client("lambda",
                                         aws_access_key_id=aws_access_key_id,
                                         aws_secret_access_key=aws_secret_access_key,
                                         region_name=region) as Λ:
            region_λs = await Λ.list_functions()

            for λ in region_λs["Functions"]:
                λ["region"] = region
                λs.append(λ)

    return λs


async def tag_lambdas(aws_access_key_id, aws_secret_access_key, λs, tags):
    """Add a set of tags to a set of lambda functions."""
    session = aiobotocore.get_session()
    for λ in λs:
        async with session.create_client("lambda",
                                         aws_access_key_id=aws_access_key_id,
                                         aws_secret_access_key=aws_secret_access_key,
                                         region_name=λ["region"]) as Λ:

            λ_tags = tags
            λ_tags["Name"] = λ["FunctionName"]
            await Λ.tag_resource(
                Resource = λ["FunctionArn"],
                Tags = λ_tags
            )


async def parse_tags(tags):
    """Return the tags in the AWS API format."""
    aws_tags = []
    for key, value in tags.items():
        aws_tags.append({'Key': key,
                         'Value': value})
    return aws_tags


################################################################################
# Skills                                                                       #
################################################################################


@match_crontab("0 * * * *")
@match_regex(r'update( aws)? tags', case_sensitive=False)
async def update_tags(opsdroid, config, message):
    try:
        aws_access_key_id = config["aws_access_key_id"]
        aws_secret_access_key = config["aws_secret_access_key"]
        regions = config['regions']
        tags = await parse_tags(config['tags'])
    except KeyError:
        _LOGGER.error("Missing config item in skill %s.",
                      config.get('name', 'aws-tag-compliance'))
        return

    _LOGGER.info("Updating instance tags...")
    if hasattr(message, 'regex'):
       await  message.respond("Updating instance tags...")
    instances = await get_instances(aws_access_key_id, aws_secret_access_key, regions)
    await tag_instances(aws_access_key_id, aws_secret_access_key, instances, tags)
    _LOGGER.info("Instance tags updated.")
    if hasattr(message, 'regex'):
        await message.respond("Updated instance tags.")

    _LOGGER.info("Updating bucket tags...")
    if hasattr(message, 'regex'):
        await message.respond("Updating bucket tags...")
    buckets = await get_buckets(aws_access_key_id, aws_secret_access_key, regions)
    await tag_buckets(aws_access_key_id, aws_secret_access_key, buckets, tags)
    _LOGGER.info("Bucket tags updated.")
    if hasattr(message, 'regex'):
        await message.respond("Updated bucket tags.")

    _LOGGER.info("Updating volume tags...")
    if hasattr(message, 'regex'):
        await message.respond("Updating volume tags...")
    volumes = await get_volumes(aws_access_key_id, aws_secret_access_key, regions)
    await tag_volumes(aws_access_key_id, aws_secret_access_key, volumes, tags)
    _LOGGER.info("Volume tags updated.")
    if hasattr(message, 'regex'):
        await message.respond("Updated volume tags.")

    _LOGGER.info("Updating ELB tags...")
    if hasattr(message, 'regex'):
        await message.respond("Updating ELB tags...")
    elbs = await get_elbs(aws_access_key_id, aws_secret_access_key, regions)
    await tag_elbs(aws_access_key_id, aws_secret_access_key, elbs, tags)
    _LOGGER.info("ELB tags updated.")
    if hasattr(message, 'regex'):
        await message.respond("Updated ELB tags.")

    _LOGGER.info("Updating lambda function tags...")
    if hasattr(message, 'regex'):
        await message.respond("Updating lambda function tags...")
    lambdas = await get_lambdas(aws_access_key_id, aws_secret_access_key, regions)
    await tag_lambdas(aws_access_key_id, aws_secret_access_key, lambdas, config['tags'])
    _LOGGER.info("Lambda function tags updated.")
    if hasattr(message, 'regex'):
        await message.respond("Updated lambda function tags.")
        await message.respond("Finished updating tags.")
