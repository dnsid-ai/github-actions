# Self-test target for the IaC workflow.
terraform {
  required_version = ">= 1.9"
}

variable "name" {
  type        = string
  description = "Bucket name."
}

# CANARY: tflint's terraform ruleset flags this unused declaration.
variable "unused" {
  type        = string
  description = "Never referenced."
  default     = ""
}

output "name" {
  value       = var.name
  description = "Echoes the input."
}
