"""
Code ingestion module for CodeMap.

This module provides functionality to ingest code from various sources:
- GitHub repositories
- Local directories
- Local files
- Multiple files

Usage:
    >>> from codemap.ingest import CodeIngestor
    >>> 
    >>> ingestor = CodeIngestor()
    >>> 
    >>> # Ingest from GitHub
    >>> result = ingestor.ingest("https://github.com/user/repo")
    >>> 
    >>> # Ingest local directory
    >>> result = ingestor.ingest("/path/to/project")
    >>> 
    >>> # Ingest single file
    >>> result = ingestor.ingest("main.py")
    >>> 
    >>> # Access files
    >>> for file in result.get_python_files():
    >>>     print(f"{file.relative_path}: {file.lines_of_code} lines")
"""

from .models import (
    CodebaseIngestion,
    CodebaseMetadata,
    FileInfo,
    SourceType,
    FileType,
)
from .ingestor import CodeIngestor
from .local_scanner import LocalScanner
from .github_loader import GitHubLoader
from .file_parser import FileParser

__all__ = [
    # Main API
    'CodeIngestor',
    
    # Data models
    'CodebaseIngestion',
    'CodebaseMetadata',
    'FileInfo',
    'SourceType',
    'FileType',
    
    # Specialized loaders (for advanced usage)
    'LocalScanner',
    'GitHubLoader',
    'FileParser',
]

__version__ = '0.1.0'