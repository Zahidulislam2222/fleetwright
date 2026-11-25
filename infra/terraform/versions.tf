terraform {
  required_version = ">= 1.16.5, < 2.0.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "6.68.0"
    }
  }
}

provider "aws" {
  region = var.region
  default_tags {
    # Global Rule 20: every member of the shared portfolio hub carries Hub and Project tags.
    tags = { Hub = var.hub, Project = var.name, ManagedBy = "Terraform", Purpose = "unprovisioned-reference" }
  }
}
