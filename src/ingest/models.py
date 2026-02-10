"""
Data models for code ingestion and representation.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any
from enum import Enum


class SourceType(Enum):
    """Type of code source."""
    GITHUB = "github"
    LOCAL_FOLDER = "local_folder"
    LOCAL_FILE = "local_file"
    ARCHIVE = "archive"


class FileType(Enum):
    """Supported file types."""
    PYTHON = ".py"
    JAVASCRIPT = ".js"
    TYPESCRIPT = ".ts"
    JAVA = ".java"
    GO = ".go"
    UNKNOWN = ""


@dataclass
class FileInfo:
    """Information about a single file."""
    path: Path
    relative_path: Path
    file_type: FileType
    size_bytes: int
    lines_of_code: int = 0
    content: Optional[str] = None
    
    def __post_init__(self):
        """Ensure paths are Path objects."""
        self.path = Path(self.path)
        self.relative_path = Path(self.relative_path)


@dataclass
class CodebaseMetadata:
    """Metadata about the entire codebase."""
    source_type: SourceType
    source_location: str
    total_files: int = 0
    total_lines: int = 0
    primary_language: Optional[str] = None
    languages: Dict[str, int] = field(default_factory=dict)  # language -> file count
    directory_structure: Dict[str, Any] = field(default_factory=dict)
    git_info: Optional[Dict[str, str]] = None  # branch, commit, remote


@dataclass
class CodebaseIngestion:
    """Complete ingestion result."""
    metadata: CodebaseMetadata
    files: List[FileInfo] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def add_file(self, file_info: FileInfo):
        """Add a file to the ingestion."""
        self.files.append(file_info)
        self.metadata.total_files += 1
        self.metadata.total_lines += file_info.lines_of_code
        if file_info.file_type != FileType.UNKNOWN:
            lang = file_info.file_type.name
            self.metadata.languages[lang] = self.metadata.languages.get(lang, 0) + 1
    
    def get_files_by_type(self, file_type: FileType) -> List[FileInfo]:
        """Get all files of a specific type."""
        return [f for f in self.files if f.file_type == file_type]
    
    def get_python_files(self) -> List[FileInfo]:
        """Convenience method to get Python files."""
        return self.get_files_by_type(FileType.PYTHON)