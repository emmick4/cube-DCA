import sys
import os
from pathlib import Path

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Add the root directory to the Python path
sys.path.insert(0, str(PROJECT_ROOT))