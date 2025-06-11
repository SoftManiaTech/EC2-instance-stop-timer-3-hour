import boto3
import datetime
import json
import os

STOP_EC2_LAMBDA_ARN = os.environ.get('STOP_EC2_LAMBDA_ARN')

def lambda_handler(event, context):
    print(f"📩 Received event: {json.dumps(event)}")

    try:
        instance_id = event['detail']['instance-id']
        region = event['region']

        ec2 = boto3.client('ec2', region_name=region)
        events = boto3.client('events', region_name=region)

        print(f"Processing instance: {instance_id} in region: {region}")

        response = ec2.describe_instances(InstanceIds=[instance_id])
        instance = response['Reservations'][0]['Instances'][0]
        tags = instance.get('Tags', [])

        if any(tag['Key'].lower() == 'autostop' and tag['Value'].lower() == 'true' for tag in tags):
            print("AutoStop=true tag found")

            stop_time = datetime.datetime.utcnow() + datetime.timedelta(hours=3)
            print("Current UTC Time:", datetime.datetime.utcnow())
            print("Scheduled Stop Time UTC:", stop_time)

            cron_expression = f"cron({stop_time.minute} {stop_time.hour} {stop_time.day} {stop_time.month} ? {stop_time.year})"
            print(f"Final cron expression: {cron_expression}")

            rule_name = f"Stop-{instance_id}-{int(datetime.datetime.now().timestamp())}"

            events.put_rule(
                Name=rule_name,
                ScheduleExpression=cron_expression,
                State='ENABLED',
                Description=f"Auto-stop EC2 instance {instance_id} after 2 minutes"
            )

            events.put_targets(
                Rule=rule_name,
                Targets=[
                    {
                        'Id': '1',
                        'Arn': STOP_EC2_LAMBDA_ARN,
                        'Input': json.dumps({'instance_id': instance_id})
                    }
                ]
            )

            print(f"Rule created and target set for instance {instance_id}")
        else:
            print(f"No valid AutoStop=true tag found. Skipping.")

        return {
            'statusCode': 200,
            'body': json.dumps(f"Instance {instance_id} processed.")
        }

    except Exception as e:
        print(f"Error occurred: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps(f"Error: {str(e)}")
        }
