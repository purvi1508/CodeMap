"""
Local file system scanner for code ingestion.
"""
from pathlib import Path
from typing import Optional, List, Set, Union

from .models import (
    CodebaseIngestion, CodebaseMetadata, SourceType,
    FileInfo
)
from .file_parser import FileParser


class LocalScanner:
    """Scanner for local file systems (folders and files)."""
    
    def __init__(self, 
                 ignore_patterns: Optional[Set[str]] = None,
                 max_file_size_mb: int = 10):
        """
        Initialize the local scanner.
        
        Args:
            ignore_patterns: Additional patterns to ignore
            max_file_size_mb: Maximum file size to process
        """
        self.parser = FileParser(ignore_patterns, max_file_size_mb)
    
    def scan_directory(self, 
                      directory_path: Union[str, Path],
                      recursive: bool = True) -> CodebaseIngestion:
        """
        Scan a local directory and all its files.
        
        Args:
            directory_path: Path to the directory
            recursive: Whether to scan subdirectories
            
        Returns:
            CodebaseIngestion object with all scanned files
        """
        dir_path = Path(directory_path).resolve()
        
        if not dir_path.exists():
            raise FileNotFoundError(f"Directory not found: {dir_path}")
        
        if not dir_path.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {dir_path}")
        
        # Initialize ingestion result
        metadata = CodebaseMetadata(
            source_type=SourceType.LOCAL_FOLDER,
            source_location=str(dir_path)
        )
        
        ingestion = CodebaseIngestion(metadata=metadata)
        
        # Get directory structure
        try:
            metadata.directory_structure = self.parser.get_directory_structure(dir_path)
        except Exception as e:
            ingestion.warnings.append(f"Could not build directory structure: {e}")
        
        # Scan files
        if recursive:
            files_to_scan = dir_path.rglob('*')
        else:
            files_to_scan = dir_path.glob('*')
        
        for file_path in files_to_scan:
            if not file_path.is_file():
                continue
            
            try:
                file_info = self.parser.parse_file(file_path, dir_path)
                if file_info:
                    ingestion.add_file(file_info)
            except Exception as e:
                ingestion.errors.append(f"Error processing {file_path}: {e}")
        
        # Determine primary language
        if metadata.languages:
            metadata.primary_language = max(
                metadata.languages.items(),
                key=lambda x: x[1]
            )[0]
        
        return ingestion
    
    def scan_file(self, file_path: Union[str, Path]) -> CodebaseIngestion:
        """
        Scan a single file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            CodebaseIngestion object with the single file
        """
        path = Path(file_path).resolve()
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        
        if not path.is_file():
            raise IsADirectoryError(f"Path is a directory, not a file: {path}")
        
        # Initialize ingestion result
        metadata = CodebaseMetadata(
            source_type=SourceType.LOCAL_FILE,
            source_location=str(path)
        )
        
        ingestion = CodebaseIngestion(metadata=metadata)
        
        # Parse the single file
        try:
            # Use parent directory as root for relative path calculation
            file_info = self.parser.parse_file(path, path.parent)
            if file_info:
                ingestion.add_file(file_info)
                metadata.primary_language = file_info.file_type.name
            else:
                ingestion.warnings.append(f"File was skipped (possibly binary or too large)")
        except Exception as e:
            ingestion.errors.append(f"Error processing file: {e}")
        
        return ingestion
    
    def scan_files(self, file_paths: List[Union[str, Path]]) -> CodebaseIngestion:
        """
        Scan multiple specific files.
        
        Args:
            file_paths: List of file paths
            
        Returns:
            CodebaseIngestion object with all files
        """
        if not file_paths:
            raise ValueError("No file paths provided")
        
        # Convert all to Path objects
        paths = [Path(p).resolve() for p in file_paths]
        
        # Find common root directory
        common_root = self._find_common_root(paths)
        
        # Initialize ingestion result
        metadata = CodebaseMetadata(
            source_type=SourceType.LOCAL_FILE,
            source_location=str(common_root) if common_root else "multiple_files"
        )
        
        ingestion = CodebaseIngestion(metadata=metadata)
        
        # Parse each file
        for path in paths:
            if not path.exists():
                ingestion.warnings.append(f"File not found: {path}")
                continue
            
            if not path.is_file():
                ingestion.warnings.append(f"Not a file: {path}")
                continue
            
            try:
                root = common_root if common_root else path.parent
                file_info = self.parser.parse_file(path, root)
                if file_info:
                    ingestion.add_file(file_info)
                else:
                    ingestion.warnings.append(f"File was skipped: {path}")
            except Exception as e:
                ingestion.errors.append(f"Error processing {path}: {e}")
        
        # Determine primary language
        if metadata.languages:
            metadata.primary_language = max(
                metadata.languages.items(),
                key=lambda x: x[1]
            )[0]
        
        return ingestion
    
    def _find_common_root(self, paths: List[Path]) -> Optional[Path]:
        """
        Find the common root directory of multiple paths.
        
        Args:
            paths: List of Path objects
            
        Returns:
            Common root Path or None if no common root
        """
        if not paths:
            return None
        
        if len(paths) == 1:
            return paths[0].parent
        
        # Get all parent sequences
        parent_sequences = [list(reversed(p.parents)) + [p] for p in paths]
        
        # Find common prefix
        common = []
        for parts in zip(*parent_sequences):
            if len(set(parts)) == 1:
                common.append(parts[0])
            else:
                break
        
        return common[-1] if common else None
    
    def get_project_info(self, directory_path: Union[str, Path]) -> dict:
        """
        Get quick project information without full scan.
        
        Args:
            directory_path: Path to the directory
            
        Returns:
            Dictionary with project information
        """
        dir_path = Path(directory_path).resolve()
        
        info = {
            'path': str(dir_path),
            'name': dir_path.name,
            'exists': dir_path.exists(),
            'is_git_repo': (dir_path / '.git').exists(),
            'has_python': False,
            'has_requirements': False,
            'has_setup_py': False,
            'has_pyproject_toml': False,
        }
        
        if not dir_path.exists():
            return info
        
        # Check for common Python project files
        info['has_requirements'] = (dir_path / 'requirements.txt').exists()
        info['has_setup_py'] = (dir_path / 'setup.py').exists()
        info['has_pyproject_toml'] = (dir_path / 'pyproject.toml').exists()
        
        # Quick check for Python files
        try:
            python_files = list(dir_path.glob('**/*.py'))
            info['has_python'] = len(python_files) > 0
            info['python_file_count'] = len(python_files)
        except Exception:
            pass
        
        return info