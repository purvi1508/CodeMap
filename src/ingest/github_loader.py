"""
GitHub repository loader and analyzer.
"""
import tempfile
import shutil
from pathlib import Path
from typing import Optional, Set, Union
import subprocess
import re

from .models import CodebaseIngestion, CodebaseMetadata, SourceType
from .local_scanner import LocalScanner

"""
Clones a GitHub repo → scans it locally → returns a structured CodebaseIngestion object with files + metadata.

Check if a URL is a GitHub repo


Input
loader.is_github_url("https://github.com/octocat/sample-project")

Output
False


Normalize GitHub URLs


Input
loader.normalize_github_url("git@github.com:octocat/sample-project.git")

Output
"https://github.com/octocat/sample-project"



Extract repo information


Input
loader.extract_repo_info("https://github.com/octocat/sample-project")

Output
{
  "owner": "octocat",
  "repo": "sample-project",
  "full_name": "octocat/sample-project",
  "url": "https://github.com/octocat/sample-project"
}


Clone the repository


Input
clone_path = loader.clone_repository(
    "https://github.com/octocat/sample-project"
)

Output
Path("/tmp/codemap_clone_abcd1234/")



Extract git metadata


Input
loader.get_git_info(Path("/tmp/codemap_clone_abcd1234"))

Output
{
  "branch": "main",
  "commit": "a1b2c3d4",
  "remote": "https://github.com/octocat/sample-project",
  "last_commit_date": "2024-11-21 10:14:03 +0000"
}



Load & analyze entire repository


Input
ingestion = loader.load_repository(
    "https://github.com/octocat/sample-project"
)

Output
CodebaseIngestion(
  metadata=CodebaseMetadata(
    source_type=SourceType.GITHUB,
    source_location="https://github.com/octocat/sample-project",
    git_info={
      "branch": "main",
      "commit": "a1b2c3d4",
      "remote": "https://github.com/octocat/sample-project",
      "last_commit_date": "2024-11-21 10:14:03 +0000"
    },
    repository_info={
      "owner": "octocat",
      "repo": "sample-project",
      "full_name": "octocat/sample-project",
      "url": "https://github.com/octocat/sample-project"
    }
  ),

  files=[
    FileInfo(
      relative_path="src/app.py",
      file_type=FileType.PYTHON,
      lines_of_code=25,
      size_bytes=812,
      content="def main(): ..."
    ),
    FileInfo(
      relative_path="src/utils.py",
      file_type=FileType.PYTHON,
      lines_of_code=14,
      size_bytes=402,
      content="def helper(): ..."
    ),
    FileInfo(
      relative_path="README.md",
      file_type=FileType.UNKNOWN,
      lines_of_code=6,
      size_bytes=128,
      content="# Sample Project"
    )
  ],

  errors=[],
  warnings=[]
)


Load a single file from GitHub


Input
single_file = loader.load_github_file(
    repo_url="https://github.com/octocat/sample-project",
    file_path="src/app.py"
)

Output
CodebaseIngestion(
  metadata=...same metadata...,
  files=[
    FileInfo(
      relative_path="src/app.py",
      file_type=FileType.PYTHON,
      lines_of_code=25,
      size_bytes=812,
      content="def main(): ..."
    )
  ],
  errors=[],
  warnings=[]
)



"""

class GitHubLoader:
    """Loader for GitHub repositories."""
    
    def __init__(self,
                 ignore_patterns: Optional[Set[str]] = None,
                 max_file_size_mb: int = 10,
                 clone_depth: Optional[int] = 1):
        """
        Initialize the GitHub loader.
        
        Args:
            ignore_patterns: Additional patterns to ignore
            max_file_size_mb: Maximum file size to process
            clone_depth: Git clone depth (None for full clone, 1 for shallow)
        """
        self.scanner = LocalScanner(ignore_patterns, max_file_size_mb)
        self.clone_depth = clone_depth
    
    def is_github_url(self, url: str) -> bool:
        """
        Check if a URL is a valid GitHub repository URL.
        
        Args:
            url: URL to check
            
        Returns:
            True if valid GitHub URL
        """
        patterns = [
            r'https?://github\.com/[\w-]+/[\w.-]+',
            r'git@github\.com:[\w-]+/[\w.-]+\.git',
            r'github\.com/[\w-]+/[\w.-]+'
        ]
        
        return any(re.match(pattern, url) for pattern in patterns)
    
    def normalize_github_url(self, url: str) -> str:
        """
        Normalize a GitHub URL to HTTPS format.
        
        Args:
            url: GitHub URL in any format
            
        Returns:
            Normalized HTTPS URL
        """
        # Remove .git suffix
        url = url.rstrip('.git')
        
        # Convert SSH to HTTPS
        if url.startswith('git@github.com:'):
            url = url.replace('git@github.com:', 'https://github.com/')
        
        # Add https:// if missing
        if not url.startswith('http'):
            url = 'https://' + url.lstrip('/')
        
        return url
    
    def extract_repo_info(self, url: str) -> dict:
        """
        Extract owner and repo name from GitHub URL.
        
        Args:
            url: GitHub URL
            
        Returns:
            Dictionary with 'owner' and 'repo' keys
        """
        normalized = self.normalize_github_url(url)
        match = re.search(r'github\.com/([\w-]+)/([\w.-]+)', normalized)
        if not match:
            raise ValueError(f"Could not extract repo info from URL: {url}")
        
        owner, repo = match.groups()
        
        return {
            'owner': owner,
            'repo': repo,
            'full_name': f"{owner}/{repo}",
            'url': normalized
        }
    
    def clone_repository(self, 
                        repo_url: str, 
                        target_dir: Optional[Path] = None,
                        branch: Optional[str] = None) -> Path:
        """
        Clone a GitHub repository.
        
        Args:
            repo_url: GitHub repository URL
            target_dir: Target directory (creates temp dir if None)
            branch: Specific branch to clone (None for default)
            
        Returns:
            Path to cloned repository
            
        Raises:
            ValueError: If URL is invalid
            subprocess.CalledProcessError: If git clone fails
        """
        if not self.is_github_url(repo_url):
            raise ValueError(f"Invalid GitHub URL: {repo_url}")
        
        normalized_url = self.normalize_github_url(repo_url)
        if target_dir is None:
            target_dir = Path(tempfile.mkdtemp(prefix='codemap_clone_'))
        else:
            target_dir = Path(target_dir)
            target_dir.mkdir(parents=True, exist_ok=True)
        cmd = ['git', 'clone']
        
        if self.clone_depth is not None:
            cmd.extend(['--depth', str(self.clone_depth)])
        
        if branch:
            cmd.extend(['--branch', branch])
        
        cmd.extend([normalized_url, str(target_dir)])
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=300  
            )
            
            return target_dir
        
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"Git clone timed out after 5 minutes")
        
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            raise RuntimeError(f"Git clone failed: {error_msg}")
    
    def get_git_info(self, repo_path: Path) -> dict:
        """
        Extract git information from a cloned repository.
        
        Args:
            repo_path: Path to git repository
            
        Returns:
            Dictionary with git information
        """
        info = {}
        
        git_dir = repo_path / '.git'
        if not git_dir.exists():
            return info
        
        try:
            result = subprocess.run(
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            info['branch'] = result.stdout.strip()
        except Exception:
            pass
        
        try:
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            info['commit'] = result.stdout.strip()[:8]  # Short hash
        except Exception:
            pass
        
        try:
            result = subprocess.run(
                ['git', 'config', '--get', 'remote.origin.url'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            info['remote'] = result.stdout.strip()
        except Exception:
            pass
        
        try:
            result = subprocess.run(
                ['git', 'log', '-1', '--format=%ci'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            info['last_commit_date'] = result.stdout.strip()
        except Exception:
            pass
        
        return info
    
    def load_repository(self,
                       repo_url: str,
                       branch: Optional[str] = None,
                       keep_clone: bool = False,
                       clone_dir: Optional[Path] = None) -> CodebaseIngestion:
        """
        Load and analyze a GitHub repository.
        
        Args:
            repo_url: GitHub repository URL
            branch: Specific branch to analyze
            keep_clone: Whether to keep cloned repository
            clone_dir: Custom clone directory (None for temp)
            
        Returns:
            CodebaseIngestion object with repository analysis
        """
        repo_info = self.extract_repo_info(repo_url)
        temp_clone = clone_dir is None
        
        try:
            clone_path = self.clone_repository(repo_url, clone_dir, branch)
            git_info = self.get_git_info(clone_path)
            ingestion = self.scanner.scan_directory(clone_path)
            
            ingestion.metadata.source_type = SourceType.GITHUB
            ingestion.metadata.source_location = repo_info['url']
            ingestion.metadata.git_info = git_info
            
            if not hasattr(ingestion.metadata, 'repository_info'):
                ingestion.metadata.repository_info = repo_info
            
            return ingestion
        
        finally:
            if temp_clone and not keep_clone and clone_dir is None:
                try:
                    if clone_path.exists():
                        shutil.rmtree(clone_path)
                except Exception as e:
                    print(f"Warning: Could not clean up temporary clone: {e}")
    
    def load_github_file(self,
                        repo_url: str,
                        file_path: str,
                        branch: Optional[str] = None) -> CodebaseIngestion:
        """
        Load a specific file from a GitHub repository.
        
        Args:
            repo_url: GitHub repository URL
            file_path: Path to file within repository
            branch: Branch name (default branch if None)
            
        Returns:
            CodebaseIngestion with single file
        """
        ingestion = self.load_repository(repo_url, branch, keep_clone=False)
        file_path_norm = Path(file_path)
        filtered_files = [
            f for f in ingestion.files 
            if f.relative_path == file_path_norm
        ]
        
        if not filtered_files:
            raise FileNotFoundError(
                f"File not found in repository: {file_path}"
            )
        new_ingestion = CodebaseIngestion(
            metadata=ingestion.metadata,
            files=filtered_files,
            errors=ingestion.errors,
            warnings=ingestion.warnings
        )
        
        return new_ingestion
    
    @staticmethod
    def is_git_installed() -> bool:
        """
        Check if git is installed and available.
        
        Returns:
            True if git is available
        """
        try:
            subprocess.run(
                ['git', '--version'],
                capture_output=True,
                check=True
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False