variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP region for deployment"
  type        = string
  default     = "europe-west3"
}

variable "service_name" {
  description = "Name of the Cloud Run service"
  type        = string
}

variable "registry_name" {
  description = "Name of the existing Artifact Registry"
  type        = string
#   default = "gcp-sandbox-nem-ai-assistant"
}

variable "image_name" {
  description = "Name of the Docker image in Artifact Registry"
  type        = string
}

variable "image_tag" {
  description = "Docker image tag"
  type        = string
}

variable "container_port" {
  description = "The port on which the container listens"
  type        = number
  # default     = 8080
}

variable "startup_probe_port" {
  description = "The port used for the startup probe"
  type        = number
  # default     = 8080
}

# variable "brand" {
#   description = "Brand name to be passed as an environment variable"
#   type        = string
#   #default     = "allplan"
# }

# variable "environment" {
#   description = "Deployment environment name to be passed as an environment variable"
#   type        = string
#   default     = "development"
# }