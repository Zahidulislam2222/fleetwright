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
    tags = { Project = var.name, ManagedBy = "Terraform", Purpose = "unprovisioned-reference" }
  }
}
