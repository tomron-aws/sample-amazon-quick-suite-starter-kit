variable "topic_id" { type = string }
variable "topic_name" { type = string }
variable "topic_description" {
  type    = string
  default = ""
}
variable "data_set_arn" { type = string }
variable "dataset_name" { type = string }

resource "aws_cloudformation_stack" "topic" {
  name = "quicksuite-topic-${var.topic_id}"

  template_body = jsonencode({
    AWSTemplateFormatVersion = "2010-09-09"
    Description              = "QuickSight Q Topic - ${var.topic_name}"
    Resources = {
      Topic = {
        Type = "AWS::QuickSight::Topic"
        Properties = {
          TopicId                = var.topic_id
          Name                   = var.topic_name
          Description            = var.topic_description
          UserExperienceVersion  = "NEW_READER_EXPERIENCE"
          DataSets = [{
            DatasetArn         = var.data_set_arn
            DatasetName        = var.dataset_name
            DatasetDescription = var.topic_description
          }]
        }
      }
    }
    Outputs = {
      TopicArn = { Value = { "Fn::GetAtt" = ["Topic", "Arn"] } }
    }
  })
}

output "topic_arn" {
  value = aws_cloudformation_stack.topic.outputs["TopicArn"]
}
