from importlib import metadata

try:
    AUTOTEST_VERSION = metadata.version("autotest")
except metadata.PackageNotFoundError:
    # Local run without installation
    AUTOTEST_VERSION = "dev"
