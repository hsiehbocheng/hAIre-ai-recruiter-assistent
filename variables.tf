variable "aws_resource_tag" {
  description = "AWS 資源標籤前綴"
  type        = string
  default     = "benson-haire"
}

variable "aws_region" {
  description = "AWS 區域"
  type        = string
  default     = "ap-southeast-1"
}

variable "resource_prefix" {
  description = "資源名稱前綴"
  type        = string
  default     = "benson-haire"
}