"""Test configuration for importing integration modules without Home Assistant."""

import sys
from pathlib import Path
from types import ModuleType

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# Importing a submodule normally executes the integration's __init__.py,
# which imports Home Assistant. These unit tests exercise standalone modules.
PACKAGE_NAME = "custom_components.georgia_natural_gas"
PACKAGE_PATH = PROJECT_ROOT / "custom_components" / "georgia_natural_gas"

package = ModuleType(PACKAGE_NAME)
package.__path__ = [str(PACKAGE_PATH)]
sys.modules.setdefault(PACKAGE_NAME, package)
