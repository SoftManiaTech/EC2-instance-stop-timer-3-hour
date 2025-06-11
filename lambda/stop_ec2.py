import boto3
import json

def lambda_handler(event, context):
    print(f"📩 Received event: {json.dumps(event)}")
    
    instance_id = None

    # Extract instance_id from various event formats
    if 'instance_id' in event:
        instance_id = event['instance_id']
    elif 'detail' in event and isinstance(event['detail'], dict):
        instance_id = event['detail'].get('instance_id')
    elif 'detail' in event and isinstance(event['detail'], str):
        try:
            instance_id = json.loads(event['detail']).get('instance_id')
        except json.JSONDecodeError:
            pass

    if not instance_id:
        print("No instance_id provided.")
        return {
            'statusCode': 400,
            'body': 'No instance_id provided'
        }

    session = boto3.session.Session()
    region = session.region_name

    ec2 = boto3.client('ec2', region_name=region)
    events = boto3.client('events', region_name=region)

    print(f"🔄 Processing instance: {instance_id} in region: {region}")

    try:
        response = ec2.describe_instances(InstanceIds=[instance_id])
        state = response['Reservations'][0]['Instances'][0]['State']['Name']
        
        if state != 'running':
            print(f"⚠️ Instance {instance_id} is not running (state: {state}). Skipping.")
            return {
                'statusCode': 200,
                'body': f"Instance {instance_id} was not running (state: {state})"
            }


        ec2.stop_instances(InstanceIds=[instance_id])
        print(f"Instance {instance_id} stopped successfully.")

        rule_name = None
        if 'resources' in event and event['resources']:
            rule_arn = event['resources'][0]
            rule_name = rule_arn.split('/')[-1] if '/' in rule_arn else rule_arn

        if not rule_name:
            rule_prefix = f"Stop-{instance_id}-"
            response = events.list_rules(NamePrefix=rule_prefix)
            if response['Rules']:
                rule_name = response['Rules'][0]['Name']

        if rule_name:
            print(f"Cleaning up EventBridge rule: {rule_name}")
            try:
                targets = events.list_targets_by_rule(Rule=rule_name)
                if targets['Targets']:
                    target_ids = [t['Id'] for t in targets['Targets']]
                    events.remove_targets(Rule=rule_name, Ids=target_ids)
                events.delete_rule(Name=rule_name)
                print(f"Rule {rule_name} deleted successfully.")
            except events.exceptions.ResourceNotFoundException:
                print(f"Rule {rule_name} not found (may be already deleted).")
            except Exception as e:
                print(f"Error deleting rule {rule_name}: {str(e)}")
        else:
            print("ℹ️ No matching EventBridge rule found to delete.")

        return {
            'statusCode': 200,
            'body': f"Instance {instance_id} stopped successfully. Rule cleanup attempted."
        }

    except ec2.exceptions.ClientError as e:
        if 'InvalidInstanceID.NotFound' in str(e):
            print(f"Instance {instance_id} not found.")
            return {
                'statusCode': 404,
                'body': f"Instance {instance_id} not found."
            }
        else:
            print(f"Unexpected EC2 error: {e}")
            raise
    except Exception as e:
        print(f"General error: {e}")
        return {
            'statusCode': 500,
            'body': f"Error stopping instance: {str(e)}"
        }
