import sys
import os


def resource_path(relative_path):
    """Returns the absolute path to the resource, whether it works in dev or in the .exe."""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)