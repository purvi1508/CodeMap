"""
File parsing utilities for code ingestion.
"""
import os
from pathlib import Path
from typing import Optional, List, Set
import mimetypes

from .models import FileInfo, FileType

"""
FileParser helps you:

Ignore irrelevant files and folders (.git, node_modules, binaries, caches, etc.)


Input
parser.should_ignore(Path("my_project/.git"))
parser.should_ignore(Path("my_project/node_modules"))
parser.should_ignore(Path("my_project/src/main.py"))
Output
True     # .git is ignored
True     # node_modules is ignored
False    # valid source file


Detect programming language by file extension

Input
parser.detect_file_type(Path("src/main.py"))
parser.detect_file_type(Path("src/helpers.js"))
parser.detect_file_type(Path("README.md"))

Output
FileType.PYTHON
FileType.JAVASCRIPT
FileType.UNKNOWN


Safely read text/code files (with size limits & encoding fallbacks)

Input
parser.read_file_safe(Path("src/main.py"))
parser.read_file_safe(Path("data.bin"))
Output
'def hello():\n    print("Hello world")\n'
None   # binary or unreadable → skipped safely


Count lines of code


Input
content = "def hello():

    print("Hello world")
"
parser.count_lines(content)

Output
2

Produce structured FileInfo objects for downstream processing

Input
from pathlib import Path

root = Path("my_project")
file_info = parser.parse_file(
    path=Path("my_project/src/main.py"),
    root_path=root
)
Output
FileInfo(
    path=Path("my_project/src/main.py"),
    relative_path=Path("src/main.py"),
    file_type=FileType.PYTHON,
    size_bytes=48,
    lines_of_code=2,
    content='def hello():\n    print("Hello world")\n'
)


Inspect directory structure up to a given depth


Input
parser.get_directory_structure(
    Path("my_project"),
    max_depth=2
)

Output
{
  "src": {
    "helpers.js": {"type": "file", "size": 58},
    "main.py": {"type": "file", "size": 48},
    "utils.py": {"type": "file", "size": 45}
  },
  "README.md": {"type": "file", "size": 18}
}


"""
class FileParser:
    """Base class for parsing and analyzing files."""
    DEFAULT_IGNORE_PATTERNS = {
        '__pycache__', '.git', '.svn', '.hg', 'node_modules',
        '.venv', 'venv', 'env', '.env', 'dist', 'build',
        '.pytest_cache', '.mypy_cache', '.tox', 'htmlcov',
        'coverage', '.coverage', 'eggs', '.eggs',
        '.pyc', '.pyo', '.pyd', '.so', '.dll', '.dylib',
        '.egg', '.egg-info', '.dist-info',
        '.idea', '.vscode', '.vs', '*.swp', '*.swo',
        '.DS_Store', 'Thumbs.db', 'desktop.ini',
    }

    EXTENSION_MAP = {
        '.py': FileType.PYTHON,
        '.js': FileType.JAVASCRIPT,
        '.jsx': FileType.JAVASCRIPT,
        '.ts': FileType.TYPESCRIPT,
        '.tsx': FileType.TYPESCRIPT,
        '.java': FileType.JAVA,
        '.go': FileType.GO,
    }
    
    def __init__(self,ignore_patterns: Optional[Set[str]] = None,max_file_size_mb: int = 10):
        """
        Initialize the file parser.
        
        Args:
            ignore_patterns: Additional patterns to ignore
            max_file_size_mb: Maximum file size to process in MB
        """
        self.ignore_patterns = self.DEFAULT_IGNORE_PATTERNS.copy()
        if ignore_patterns:
            self.ignore_patterns.update(ignore_patterns)
        
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024
    
    def should_ignore(self, path: Path) -> bool:
        """
        Check if a path should be ignored.
        
        Args:
            path: Path to check
            
        Returns:
            True if path should be ignored
        """
        path_str = str(path)
        name = path.name
        if name in self.ignore_patterns:
            return True
        for parent in path.parents:
            if parent.name in self.ignore_patterns:
                return True
        if any(path_str.endswith(pattern) for pattern in self.ignore_patterns if pattern.startswith('*')):
            return True
        if name.startswith('.') and name not in {'.env.example', '.gitignore'}:
            return True
        
        return False
    
    def detect_file_type(self, path: Path) -> FileType:
        """
        Detect the type of file based on extension.
        
        Args:
            path: Path to the file
            
        Returns:
            FileType enum value
        """
        suffix = path.suffix.lower()
        return self.EXTENSION_MAP.get(suffix, FileType.UNKNOWN)
    
    def is_text_file(self, path: Path) -> bool:
        """
        Check if a file is a text file.
        
        Args:
            path: Path to the file
            
        Returns:
            True if file is text
        """
        if self.detect_file_type(path) != FileType.UNKNOWN:
            return True
        mime_type, _ = mimetypes.guess_type(str(path))
        if mime_type and mime_type.startswith('text/'):
            return True
        try:
            with open(path, 'r', encoding='utf-8') as f:
                f.read(1024)  # Try reading first 1KB
            return True
        except (UnicodeDecodeError, PermissionError):
            return False
    
    def count_lines(self, content: str) -> int:
        """
        Count non-empty lines in content.
        
        Args:
            content: File content
            
        Returns:
            Number of non-empty lines
        """
        return len([line for line in content.split('\n') if line.strip()])
    
    def read_file_safe(self, path: Path) -> Optional[str]:
        """
        Safely read a file's content.
        
        Args:
            path: Path to the file
            
        Returns:
            File content or None if reading failed
        """
        try:
            size = path.stat().st_size
            if size > self.max_file_size_bytes:
                return None
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        except (UnicodeDecodeError, PermissionError, OSError):
            try:
                with open(path, 'r', encoding='latin-1') as f:
                    return f.read()
            except Exception:
                return None
    
    def parse_file(self, path: Path, root_path: Path) -> Optional[FileInfo]:
        """
        Parse a single file and create FileInfo.
        
        Args:
            path: Absolute path to the file
            root_path: Root path for calculating relative path
            
        Returns:
            FileInfo object or None if file should be skipped
        """
        if self.should_ignore(path):
            return None
        
        if not path.is_file():
            return None
        
        file_type = self.detect_file_type(path)
        if file_type == FileType.UNKNOWN and not self.is_text_file(path):
            return None
        
        try:
            size_bytes = path.stat().st_size
            if size_bytes > self.max_file_size_bytes:
                return None
            content = self.read_file_safe(path)
            if content is None:
                return None
            try:
                relative_path = path.relative_to(root_path)
            except ValueError:
                relative_path = path
            lines = self.count_lines(content)
            
            return FileInfo(
                path=path,
                relative_path=relative_path,
                file_type=file_type,
                size_bytes=size_bytes,
                lines_of_code=lines,
                content=content
            )
        
        except Exception as e:
            print(f"Error parsing file {path}: {e}")
            return None
    
    def find_python_files(self, root_path: Path) -> List[Path]:
        """
        Find all Python files in a directory tree.
        
        Args:
            root_path: Root directory to search
            
        Returns:
            List of Python file paths
        """
        python_files = []
        
        for path in root_path.rglob('*.py'):
            if not self.should_ignore(path):
                python_files.append(path)
        
        return python_files
    
    def get_directory_structure(self, root_path: Path, max_depth: int = 3) -> dict:
        """
        Create a nested dictionary representing the directory structure.
        
        Args:
            root_path: Root directory
            max_depth: Maximum depth to traverse
            
        Returns:
            Nested dictionary of directory structure
        """
        def _build_tree(path: Path, current_depth: int) -> dict:
            if current_depth > max_depth:
                return {}
            
            tree = {}
            
            try:
                for item in sorted(path.iterdir()):
                    if self.should_ignore(item):
                        continue
                    
                    if item.is_dir():
                        tree[item.name] = _build_tree(item, current_depth + 1)
                    elif item.is_file():
                        tree[item.name] = {
                            'type': 'file',
                            'size': item.stat().st_size
                        }
            except PermissionError:
                pass
            
            return tree
        
        return _build_tree(root_path, 0)