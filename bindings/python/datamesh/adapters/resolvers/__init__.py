from __future__ import annotations

from datamesh.adapters.resolvers.github import GitHubAdapter
from datamesh.adapters.resolvers.http import HttpAdapter
from datamesh.adapters.resolvers.kaggle import KaggleAdapter
from datamesh.adapters.resolvers.local_file import LocalFileAdapter

__all__ = [
    "LocalFileAdapter",
    "GitHubAdapter",
    "KaggleAdapter",
    "HttpAdapter",
]
