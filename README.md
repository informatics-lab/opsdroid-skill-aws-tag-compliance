# opsdroid skill aws tag compliance

A skill for [opsdroid](https://github.com/opsdroid/opsdroid) to consistently ensure certain tags are applied to AWS resources.

## Requirements

An AWS account with access keys which can update EC2 and S3 resource tags.

## Configuration

```yaml
  - name: aws-tag-compliance
    aws_access_key_id: "MYACCESSKEY"
    aws_secret_access_key: "MYSECRETKEY"
    regions:
      - "eu-west-1"
    tags:
      Tag1: 'value1'
      Tag2: 'value2'
```
## Usage

#### `update AWS tags`

Updates all tags specified in the configuration. This also runs hourly via crontab.

> user: update AWS tags
>
> opsdroid: Updating the tags...
> opsdroid: Tags updated.
