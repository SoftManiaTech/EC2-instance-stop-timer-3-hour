provider "aws" {
  region     = var.region
  access_key = var.aws_access_key
  secret_key = var.aws_secret_key
}

data "aws_caller_identity" "current" {}

# Lambda Execution Role
resource "aws_iam_role" "lambda_role" {
  name = "LambdaEC2StopperRole"
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect = "Allow",
      Principal = {
        Service = "lambda.amazonaws.com"
      },
      Action = "sts:AssumeRole"
    }]
  })
}

# Attach Policy to Role
resource "aws_iam_role_policy" "lambda_policy" {
  name   = "LambdaEC2Policy"
  role   = aws_iam_role.lambda_role.id
  policy = file("iam_policies/lambda_role_policy.json")
}

# Archive Lambda Code
data "archive_file" "stop_lambda" {
  type        = "zip"
  source_file = "${path.module}/lambda/stop_ec2.py"
  output_path = "${path.module}/lambda/stop_ec2.zip"
}

data "archive_file" "schedule_lambda" {
  type        = "zip"
  source_file = "${path.module}/lambda/schedule_stop.py"
  output_path = "${path.module}/lambda/schedule_stop.zip"
}

# Stop Lambda
resource "aws_lambda_function" "stop_ec2" {
  function_name = var.stop_lambda_name
  role          = aws_iam_role.lambda_role.arn
  handler       = "stop_ec2.lambda_handler"
  runtime       = "python3.9"
  timeout       = var.lambda_timeout
  filename      = data.archive_file.stop_lambda.output_path
}

# Schedule Lambda
resource "aws_lambda_function" "schedule_lambda" {
  function_name = var.schedule_lambda_name
  role          = aws_iam_role.lambda_role.arn
  handler       = "schedule_stop.lambda_handler"
  runtime       = "python3.9"
  timeout       = var.lambda_timeout
  filename      = data.archive_file.schedule_lambda.output_path

  environment {
    variables = {
      STOP_EC2_LAMBDA_ARN = aws_lambda_function.stop_ec2.arn
    }
  }
}

# Event Rule: Trigger on EC2 Start
resource "aws_cloudwatch_event_rule" "ec2_start_rule" {
  name        = "TriggerLambdaOnEC2Start"
  description = "Trigger Schedule Lambda on EC2 start"
  event_pattern = jsonencode({
    "source": ["aws.ec2"],
    "detail-type": ["EC2 Instance State-change Notification"],
    "detail": {
      "state": ["running"]
    }
  })
}

# CloudWatch Target → Schedule Lambda
resource "aws_cloudwatch_event_target" "trigger_lambda_target" {
  rule      = aws_cloudwatch_event_rule.ec2_start_rule.name
  target_id = "TriggerScheduleLambda"
  arn       = aws_lambda_function.schedule_lambda.arn
}

# Permission for CloudWatch to trigger schedule_lambda
resource "aws_lambda_permission" "allow_eventbridge_schedule" {
  statement_id  = "AllowScheduleInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.schedule_lambda.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.ec2_start_rule.arn
}

# ✅ Permission for EventBridge to trigger stop_ec2 Lambda
resource "aws_lambda_permission" "allow_eventbridge_stop_lambda" {
  statement_id  = "stopec2"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.stop_ec2.function_name
  principal     = "events.amazonaws.com"
  source_arn    = "arn:aws:events:${var.region}:${data.aws_caller_identity.current.account_id}:rule/Stop-*"
}
