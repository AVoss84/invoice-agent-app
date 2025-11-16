terraform {
  backend "gcs" {
    bucket = "invoice-agent-storage "                           # Cloud Storage bucket name
    prefix = "terraform/terraform.tfstate" # Path for storing Terraform state
  }
}

locals {
  env_vars = {
    # "BRAND_NAME"                              = var.brand
    "GCP_PROJECT"                             = var.project_id
    # "ENVIRONMENT"                             = var.environment

  }
}

# resource "google_artifact_registry_repository" "docker" {
#   project       = var.project_id
#   location      = var.region
#   repository_id = var.registry_name
#   format        = "DOCKER"
# }

# Deployer Service Account
resource "google_service_account" "my_deployer" {
  project      = var.project_id
  account_id   = "crd-sa-invoice" # Ensure account_id is within 30 characters
  display_name = "Cloud Run Deployer Service Account"
}

# Runtime Service Account
resource "google_service_account" "my_run_time" {
  project      = var.project_id
  account_id   = "crrt-sa-invoice" 
  display_name = "Cloud Run Run Time Service Account"
}


# Grant Deployer Service Account permissions to deploy to Cloud Run
resource "google_service_account_iam_member" "allow_deployer_to_act_as_runtime_sa" {
  service_account_id = google_service_account.my_run_time.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.my_deployer.email}"
}

# # Grant permissions to the runtime service account for various services
# # To invoke Cloud Run service of Agbe here
# resource "google_cloud_run_service_iam_member" "invoker_binding" {
#   location = var.region
#   service  = "ai-assistant-backend-service-${substr(var.brand, 0, 10)}" # Iterates over each service in the list
#   role     = "roles/run.invoker"
#   member   = "serviceAccount:${google_service_account.my_run_time.email}"
# }

# Define Cloud Run Service
resource "google_cloud_run_service" "my_gcr_service" {
  
  #provider = google-beta
  name     = var.service_name
  location = var.region
  project  = var.project_id
  metadata {
    annotations = {
      "run.googleapis.com/ingress" = "all"    # "internal-and-cloud-load-balancing" "internal"
    }
    # labels = {
    #   project = "agentic-backend-${var.brand}"
    #   team   = "neme-ai-rnd"
    #   brand  = var.brand
    # }
  }

  timeouts {
    create = "10m"
    update = "10m"
    delete = "10m"
  }

  template {
    metadata {
      annotations = {
        "run.googleapis.com/client-name" = "terraform"
        "run.googleapis.com/network-interfaces" = jsonencode([{
          network    = "projects/neme-ai-rnd-dev-net-spoke-0/global/networks/dev-spoke-0"
          subnetwork = "projects/neme-ai-rnd-dev-net-spoke-0/regions/europe-west3/subnetworks/dev-default"
          # Optional: Add network tags for firewall rules
          tags = ["allow-egress-internet"]
        }])
             "run.googleapis.com/vpc-access-egress" = "all-traffic"
        # Avoid cold starts by setting minScale to 1
        "autoscaling.knative.dev/minScale" = "1"
      }
    }

    spec {
      # Increase the timeout to 300 seconds (adjust as needed)
      timeout_seconds      = 300
      # service_account_name = "github-deployer-sa-dev@neme-ai-rnd-dev-prj-01.iam.gserviceaccount.com"
      service_account_name = google_service_account.my_run_time.email
      containers {
        image = "${var.region}-docker.pkg.dev/${var.project_id}/${var.registry_name}/${var.image_name}:${var.image_tag}"
        # Define environment variables
        dynamic "env" {
          # local.env_vars
          for_each = local.env_vars
          content {
            name  = env.key
            value = env.value
          }
        }        
        ports {
          container_port = var.container_port
        }
        startup_probe {
          initial_delay_seconds = 30
          timeout_seconds       = 10
          period_seconds        = 30
          failure_threshold     = 10
          tcp_socket {
            port = var.startup_probe_port
          }
        }

        # Increase resource limits: allocate more memory and optionally CPU
        resources {
          limits = {
            memory = "2Gi"
            cpu    = "2" # number of CPU cores
          }
        }
      }
    }
  }

  autogenerate_revision_name = true

  lifecycle {
    prevent_destroy = false
  }
}
