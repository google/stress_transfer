"""Make the cloud API functions work."""
import os
import sys


def AddAppEngineLibraries():
  """Add gae zipped libraries into path.

  Run before any imports that requires those zipped libraries.
  """
  dirname = os.path.dirname(__file__)
  for lib_name in os.listdir(dirname):
    if lib_name.endswith('.zip'):
      lib_path = os.path.join(dirname, lib_name)
      if lib_path not in sys.path:
        sys.path.insert(0, lib_path)

# Don't worry. Python only runs this once.
AddAppEngineLibraries()
