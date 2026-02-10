"""
API detector - detects and analyzes API endpoints from web frameworks.
"""
import ast
from typing import List, Optional, Dict
from pathlib import Path

from .models import APIEndpoint, APIAnalysisResult, FunctionInfo, Parameter
from .ast_analyzer import ASTAnalyzer


class APIDetector:
    """Detects API endpoints from web framework code."""
    
    def __init__(self):
        """Initialize the API detector."""
        self.ast_analyzer = ASTAnalyzer()
    
    def detect_framework(self, content: str) -> Optional[str]:
        """
        Detect which web framework is being used.
        
        Args:
            content: File content
            
        Returns:
            Framework name ('flask', 'fastapi', 'django') or None
        """
        content_lower = content.lower()
        
        # Check for Flask
        if 'from flask import' in content_lower or 'import flask' in content_lower:
            return 'flask'
        
        # Check for FastAPI
        if 'from fastapi import' in content_lower or 'import fastapi' in content_lower:
            return 'fastapi'
        
        # Check for Django
        if 'from django' in content_lower or 'django.http' in content_lower:
            return 'django'
        
        return None
    
    def analyze_file(self, file_path: Path, content: str) -> Optional[APIAnalysisResult]:
        """
        Analyze a file for API endpoints.
        
        Args:
            file_path: Path to the file
            content: File content
            
        Returns:
            APIAnalysisResult or None if no API framework detected
        """
        framework = self.detect_framework(content)
        
        if not framework:
            return None
        
        result = APIAnalysisResult(framework=framework)
        
        if framework == 'flask':
            result.endpoints = self._extract_flask_endpoints(content, file_path)
        elif framework == 'fastapi':
            result.endpoints = self._extract_fastapi_endpoints(content, file_path)
        elif framework == 'django':
            result.endpoints = self._extract_django_endpoints(content, file_path)
        
        return result
    
    def _extract_flask_endpoints(self, content: str, file_path: Path) -> List[APIEndpoint]:
        """Extract Flask route decorators."""
        endpoints = []
        
        try:
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # Check for route decorators
                    for decorator in node.decorator_list:
                        endpoint = self._parse_flask_decorator(decorator, node, file_path)
                        if endpoint:
                            endpoints.append(endpoint)
        
        except SyntaxError:
            pass
        
        return endpoints
    
    def _parse_flask_decorator(self, decorator: ast.expr, 
                              func_node: ast.FunctionDef, 
                              file_path: Path) -> Optional[APIEndpoint]:
        """Parse a Flask decorator to extract endpoint info."""
        # Handle @app.route('/path') or @bp.route('/path')
        if isinstance(decorator, ast.Call):
            if isinstance(decorator.func, ast.Attribute):
                if decorator.func.attr == 'route':
                    # Extract path
                    path = None
                    methods = ['GET']  # Default
                    
                    if decorator.args:
                        if isinstance(decorator.args[0], ast.Constant):
                            path = decorator.args[0].value
                    
                    # Extract methods from keywords
                    for keyword in decorator.keywords:
                        if keyword.arg == 'methods':
                            if isinstance(keyword.value, ast.List):
                                methods = [
                                    elt.value for elt in keyword.value.elts
                                    if isinstance(elt, ast.Constant)
                                ]
                    
                    if path:
                        # Create endpoint for each method
                        endpoints = []
                        for method in methods:
                            endpoint = APIEndpoint(
                                path=path,
                                method=method,
                                function_name=func_node.name,
                                decorators=[self.ast_analyzer._get_decorator_name(d) for d in func_node.decorator_list],
                                parameters=self.ast_analyzer._extract_parameters(func_node.args),
                                module=file_path.stem,
                                line_number=func_node.lineno
                            )
                            endpoints.append(endpoint)
                        
                        return endpoints[0] if endpoints else None
        
        return None
    
    def _extract_fastapi_endpoints(self, content: str, file_path: Path) -> List[APIEndpoint]:
        """Extract FastAPI route decorators."""
        endpoints = []
        
        try:
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Check for HTTP method decorators
                    for decorator in node.decorator_list:
                        endpoint = self._parse_fastapi_decorator(decorator, node, file_path)
                        if endpoint:
                            endpoints.append(endpoint)
        
        except SyntaxError:
            pass
        
        return endpoints
    
    def _parse_fastapi_decorator(self, decorator: ast.expr,
                                func_node: ast.FunctionDef | ast.AsyncFunctionDef,
                                file_path: Path) -> Optional[APIEndpoint]:
        """Parse a FastAPI decorator to extract endpoint info."""
        # Handle @app.get('/path'), @app.post('/path'), etc.
        if isinstance(decorator, ast.Call):
            if isinstance(decorator.func, ast.Attribute):
                method = decorator.func.attr.upper()
                
                # Check if it's an HTTP method
                if method in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD']:
                    path = None
                    
                    if decorator.args:
                        if isinstance(decorator.args[0], ast.Constant):
                            path = decorator.args[0].value
                    
                    if path:
                        return APIEndpoint(
                            path=path,
                            method=method,
                            function_name=func_node.name,
                            decorators=[self.ast_analyzer._get_decorator_name(d) for d in func_node.decorator_list],
                            parameters=self.ast_analyzer._extract_parameters(func_node.args),
                            module=file_path.stem,
                            line_number=func_node.lineno
                        )
        
        return None
    
    def _extract_django_endpoints(self, content: str, file_path: Path) -> List[APIEndpoint]:
        """Extract Django view functions/classes."""
        endpoints = []
        
        # Django endpoints are typically defined in urls.py
        # This is a simplified version - full Django support would need url pattern parsing
        
        try:
            tree = ast.parse(content)
            
            # Look for view functions (functions that take request as first param)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    if node.args.args and node.args.args[0].arg == 'request':
                        # This is likely a Django view
                        endpoint = APIEndpoint(
                            path="<defined in urls.py>",
                            method="ANY",
                            function_name=node.name,
                            decorators=[self.ast_analyzer._get_decorator_name(d) for d in node.decorator_list],
                            parameters=self.ast_analyzer._extract_parameters(node.args),
                            module=file_path.stem,
                            line_number=node.lineno
                        )
                        endpoints.append(endpoint)
        
        except SyntaxError:
            pass
        
        return endpoints
    
    def generate_api_summary(self, result: APIAnalysisResult) -> Dict:
        """
        Generate a summary of the API.
        
        Args:
            result: API analysis result
            
        Returns:
            Dictionary with API summary
        """
        endpoint_count = result.get_endpoint_count()
        
        paths = list(set(ep.path for ep in result.endpoints))
        
        return {
            'framework': result.framework,
            'total_endpoints': len(result.endpoints),
            'unique_paths': len(paths),
            'methods': endpoint_count,
            'paths': sorted(paths)
        }
    
    def detect_rest_patterns(self, result: APIAnalysisResult) -> Dict[str, List[str]]:
        """
        Detect RESTful patterns in the API.
        
        Args:
            result: API analysis result
            
        Returns:
            Dictionary with detected patterns
        """
        patterns = {
            'resource_endpoints': [],  # /users, /posts, etc.
            'nested_resources': [],    # /users/{id}/posts
            'action_endpoints': [],    # /users/{id}/activate
            'collection_endpoints': [],  # /users
            'item_endpoints': []       # /users/{id}
        }
        
        for endpoint in result.endpoints:
            path = endpoint.path
            
            # Resource endpoints (plural nouns)
            if '/' in path:
                parts = [p for p in path.split('/') if p and not p.startswith('{')]
                if parts:
                    patterns['resource_endpoints'].append(parts[0])
            
            # Nested resources
            if path.count('/') > 2 and '{' in path:
                patterns['nested_resources'].append(path)
            
            # Action endpoints (verbs)
            action_verbs = ['activate', 'deactivate', 'send', 'process', 'validate']
            for verb in action_verbs:
                if verb in path.lower():
                    patterns['action_endpoints'].append(path)
                    break
            
            # Collection vs item endpoints
            if '{' in path or '<' in path:
                patterns['item_endpoints'].append(path)
            else:
                patterns['collection_endpoints'].append(path)
        
        # Remove duplicates
        for key in patterns:
            patterns[key] = sorted(set(patterns[key]))
        
        return patterns
    
    def check_rest_conventions(self, result: APIAnalysisResult) -> List[str]:
        """
        Check if API follows REST conventions.
        
        Args:
            result: API analysis result
            
        Returns:
            List of convention violations
        """
        violations = []
        
        for endpoint in result.endpoints:
            path = endpoint.path
            method = endpoint.method
            
            # Check for verbs in URL (should use HTTP methods instead)
            action_verbs = ['get', 'create', 'update', 'delete', 'add', 'remove']
            for verb in action_verbs:
                if f'/{verb}' in path.lower():
                    violations.append(
                        f"{method} {path}: Contains action verb '{verb}' - use HTTP methods instead"
                    )
            
            # Check for proper plural nouns in resource endpoints
            parts = [p for p in path.split('/') if p and not p.startswith('{')]
            if parts:
                resource = parts[0]
                # Check if GET on collection uses singular
                if method == 'GET' and not ('{' in path or '<' in path):
                    if not resource.endswith('s') and resource != 'data':
                        violations.append(
                            f"{method} {path}: Collection endpoint should use plural noun"
                        )
            
            # Check for inconsistent paths
            if method == 'POST' and ('{' in path or '<' in path):
                violations.append(
                    f"{method} {path}: POST should typically be on collection, not item"
                )
        
        return violations