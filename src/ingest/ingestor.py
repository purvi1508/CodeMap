"""
Main ingestion orchestrator - unified interface for all code sources.
"""
from pathlib import Path
from typing import Union, Optional, List, Set
from urllib.parse import urlparse

from .models import CodebaseIngestion, SourceType
from .local_scanner import LocalScanner
from .github_loader import GitHubLoader


class CodeIngestor:
    """
    Unified interface for ingesting code from various sources.
    
    This is the main entry point for code ingestion.
    """
    
    def __init__(self,
                 ignore_patterns: Optional[Set[str]] = None,
                 max_file_size_mb: int = 10,
                 git_clone_depth: Optional[int] = 1):
        """
        Initialize the code ingestor.
        
        Args:
            ignore_patterns: Additional patterns to ignore
            max_file_size_mb: Maximum file size to process
            git_clone_depth: Depth for git clones (1 for shallow, None for full)
        """
        self.local_scanner = LocalScanner(ignore_patterns, max_file_size_mb)
        self.github_loader = GitHubLoader(ignore_patterns, max_file_size_mb, git_clone_depth)
        self.ignore_patterns = ignore_patterns
        self.max_file_size_mb = max_file_size_mb
    
    def ingest(self, 
               source: Union[str, Path, List[Union[str, Path]]],
               **kwargs) -> CodebaseIngestion:
        """
        Ingest code from any source (auto-detects source type).
        
        Args:
            source: Can be:
                - GitHub URL (str)
                - Local directory path (str or Path)
                - Local file path (str or Path)
                - List of file paths
            **kwargs: Additional arguments passed to specific loaders
            
        Returns:
            CodebaseIngestion object
            
        Examples:
            >>> ingestor = CodeIngestor()
            >>> 
            >>> # GitHub repository
            >>> result = ingestor.ingest("https://github.com/user/repo")
            >>> 
            >>> # Local folder
            >>> result = ingestor.ingest("/path/to/project")
            >>> 
            >>> # Single file
            >>> result = ingestor.ingest("/path/to/file.py")
            >>> 
            >>> # Multiple files
            >>> result = ingestor.ingest(["file1.py", "file2.py"])
        """
        # Handle list of files
        if isinstance(source, list):
            return self.ingest_files(source)
        
        source_str = str(source)
        
        # Detect source type
        if self._is_github_url(source_str):
            return self.ingest_github(source_str, **kwargs)
        
        path = Path(source_str)
        
        if path.is_dir():
            return self.ingest_directory(path, **kwargs)
        
        if path.is_file():
            return self.ingest_file(path)
        
        # If path doesn't exist, might be a malformed GitHub URL
        if 'github' in source_str.lower():
            try:
                return self.ingest_github(source_str, **kwargs)
            except Exception as e:
                raise ValueError(
                    f"Source appears to be a GitHub URL but is invalid: {e}"
                )
        
        raise ValueError(
            f"Could not determine source type or source does not exist: {source}"
        )
    
    def ingest_github(self,
                     repo_url: str,
                     branch: Optional[str] = None,
                     keep_clone: bool = False,
                     clone_dir: Optional[Path] = None) -> CodebaseIngestion:
        """
        Ingest code from a GitHub repository.
        
        Args:
            repo_url: GitHub repository URL
            branch: Specific branch to analyze
            keep_clone: Whether to keep the cloned repository
            clone_dir: Directory to clone into
            
        Returns:
            CodebaseIngestion object
        """
        if not GitHubLoader.is_git_installed():
            raise RuntimeError(
                "Git is not installed. Please install git to use GitHub integration."
            )
        
        return self.github_loader.load_repository(
            repo_url=repo_url,
            branch=branch,
            keep_clone=keep_clone,
            clone_dir=clone_dir
        )
    
    def ingest_directory(self,
                        directory_path: Union[str, Path],
                        recursive: bool = True) -> CodebaseIngestion:
        """
        Ingest code from a local directory.
        
        Args:
            directory_path: Path to directory
            recursive: Whether to scan subdirectories
            
        Returns:
            CodebaseIngestion object
        """
        return self.local_scanner.scan_directory(
            directory_path=directory_path,
            recursive=recursive
        )
    
    def ingest_file(self, file_path: Union[str, Path]) -> CodebaseIngestion:
        """
        Ingest a single file.
        
        Args:
            file_path: Path to file
            
        Returns:
            CodebaseIngestion object
        """
        return self.local_scanner.scan_file(file_path)
    
    def ingest_files(self, 
                    file_paths: List[Union[str, Path]]) -> CodebaseIngestion:
        """
        Ingest multiple specific files.
        
        Args:
            file_paths: List of file paths
            
        Returns:
            CodebaseIngestion object
        """
        return self.local_scanner.scan_files(file_paths)
    
    def _is_github_url(self, source: str) -> bool:
        """
        Check if source string is a GitHub URL.
        
        Args:
            source: Source string
            
        Returns:
            True if appears to be GitHub URL
        """
        # Quick checks
        if 'github.com' in source.lower():
            return True
        
        if source.startswith('git@github.com:'):
            return True
        
        # Use GitHub loader's validation
        return self.github_loader.is_github_url(source)
    
    def get_source_info(self, source: Union[str, Path]) -> dict:
        """
        Get information about a source without full ingestion.
        
        Args:
            source: Source path or URL
            
        Returns:
            Dictionary with source information
        """
        source_str = str(source)
        
        info = {
            'source': source_str,
            'type': None,
            'exists': False,
            'readable': False
        }
        
        # GitHub URL
        if self._is_github_url(source_str):
            info['type'] = 'github'
            try:
                repo_info = self.github_loader.extract_repo_info(source_str)
                info.update(repo_info)
                info['readable'] = GitHubLoader.is_git_installed()
            except Exception as e:
                info['error'] = str(e)
            return info
        
        # Local path
        path = Path(source_str)
        info['exists'] = path.exists()
        
        if path.exists():
            info['readable'] = True
            
            if path.is_dir():
                info['type'] = 'directory'
                # Get quick project info
                try:
                    project_info = self.local_scanner.get_project_info(path)
                    info.update(project_info)
                except Exception as e:
                    info['error'] = str(e)
            
            elif path.is_file():
                info['type'] = 'file'
                info['size_bytes'] = path.stat().st_size
                info['name'] = path.name
        
        return info
    
    def validate_source(self, source: Union[str, Path]) -> tuple[bool, str]:
        """
        Validate if a source can be ingested.
        
        Args:
            source: Source path or URL
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            info = self.get_source_info(source)
            
            if info['type'] == 'github':
                if not info.get('readable'):
                    return False, "Git is not installed"
                return True, "Valid GitHub repository"
            
            if not info.get('exists'):
                return False, f"Path does not exist: {source}"
            
            if not info.get('readable'):
                return False, f"Path is not readable: {source}"
            
            if info['type'] is None:
                return False, "Unknown source type"
            
            return True, f"Valid {info['type']}"
        
        except Exception as e:
            return False, f"Validation error: {e}"