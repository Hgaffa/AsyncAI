"""Sphinx configuration for asyncai documentation."""
import os
import sys

# Allow sphinx to import the asyncai package from the project root
sys.path.insert(0, os.path.abspath(".."))


project = "asyncai"
author = "asyncai contributors"
release = "0.1.0"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "sqlalchemy": ("https://docs.sqlalchemy.org/en/20/", None),
    "pydantic": ("https://docs.pydantic.dev/latest/", None),
}

html_theme = "furo"
autodoc_member_order = "bysource"
autodoc_typehints = "description"
