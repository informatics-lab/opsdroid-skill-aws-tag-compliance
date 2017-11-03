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


async def tag_buckets(aws_access_key_id, aws_secret_access_key, buckets, tags):
    """Add a set of tags to a set of buckets."""
    session = aiobotocore.get_session()
    for bucket in buckets:
        async with session.create_client("s3",
                                         aws_access_key_id=aws_access_key_id,
                                         aws_secret_access_key=aws_secret_access_key,
                                         region_name=bucket["region"]) as s3:
            await s3.put_bucket_tagging(
                Bucket = bucket["Name"],
                Tagging = {'TagSet': tags}
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
@match_regex(r'update( aws|ec2|instance)? tags', case_sensitive=False)
async def update_tags(opsdroid, config, message):
    try:
        aws_access_key_id = config["aws_access_key_id"]
    except KeyError:
        _LOGGER.error("Missing config item 'aws_access_key_id' in skill %s.",
                      config.get('name', 'aws-tag-compliance'))
        return

    try:
        aws_secret_access_key = config["aws_secret_access_key"]
    except KeyError:
        _LOGGER.error("Missing config item 'regions' in skill %s.",
                      config.get('name', 'aws-tag-compliance'))
        return

    try:
        regions = config['regions']
    except KeyError:
        _LOGGER.error("Missing config item 'regions' in skill %s."
                      "Must be a list of regions.",
                      config.get('name', 'aws-tag-compliance'))
        return

    try:
        tags = await parse_tags(config['tags'])
    except KeyError:
        _LOGGER.error("Missing config item 'tags' in skill %s."
                      "Must be a dictionary of tags to implement.",
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
