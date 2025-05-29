import os
from pathlib import Path

# Determine the environment: "vm" (local machine) or "docker" (container local or remote)
using = "vm"
# using = "docker"

package_root = Path(__file__).parent.parent.parent.parent

# -----------------------------------------------------------
# Define defaults based on the environment
match using:
    case "vm":
        defaults = {
            "CODE_DIR": str(package_root / "src"),
            "DATA_PKG_DIR": str(package_root / "data"),  # internal data folder
            "GCP_PROJECT": "neme-ai-rnd-dev-prj-01",
            "MODEL_PROVIDER": "google",  # ollama
        }
    case "docker":
        defaults = {
            "CODE_DIR": "/app/src/",
            "DATA_PKG_DIR": "/app/data/",
            "GCP_PROJECT": "neme-ai-rnd-dev-prj-01",
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
GCP_PROJECT = os.environ["GCP_PROJECT"]
MODEL_PROVIDER = os.environ["MODEL_PROVIDER"]
