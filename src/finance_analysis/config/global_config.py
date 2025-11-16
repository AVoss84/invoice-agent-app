import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Environment: "local", "local-docker", "deployment"
using = "local"
# using = "local-docker"
# using = "deployment"

package_root = Path(__file__).resolve().parents[3]


# -----------------------------------------------------------
# Define defaults based on the environment
match using:
    case "local":
        defaults = {
            "CODE_DIR": str(package_root / "src"),
            "DATA_PKG_DIR": str(package_root / "data"),  # internal data folder
            "MODEL_PROVIDER": "google",  # ollama
        }
    case "local-docker" | "deployment":
        defaults = {
            "CODE_DIR": "/app/src/",
            "DATA_PKG_DIR": "/app/data/",
            "MODEL_PROVIDER": "google",
        }
    case _:
        raise ValueError(f"Unknown environment: {using}")

# -----------------------------------------------------------
# Set environment variables with defaults if not already set
for env in defaults.keys():
    os.environ[env] = defaults[env]

CODE_DIR = os.environ["CODE_DIR"]
DATA_PKG_DIR = os.environ["DATA_PKG_DIR"]
GCP_PROJECT = os.getenv("GCP_PROJECT")
MODEL_PROVIDER = os.environ["MODEL_PROVIDER"]
