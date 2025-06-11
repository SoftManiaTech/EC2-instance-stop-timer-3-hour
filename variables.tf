variable "aws_access_key" {
  description = "AWS access key"
  type        = string
  sensitive   = true
}

variable "aws_secret_key" {
  description = "AWS secret key"
  type        = string
  sensitive   = true
}

variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "stop_lambda_name" {
  description = "Name of the stop EC2 Lambda function"
  type        = string
}

variable "schedule_lambda_name" {
  description = "Name of the schedule Lambda function"
  type        = string
}

variable "lambda_timeout" {
  description = "Timeout for Lambda functions in seconds"
  type        = number
  default     = 30
}