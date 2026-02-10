"""
Code analyzers module for CodeMap.

This module provides comprehensive code analysis capabilities including:
- AST parsing and structure extraction
- Class hierarchy and relationship analysis
- Function call graph generation
- Module dependency mapping
- API endpoint detection (Flask, FastAPI, Django)

Usage:
    >>> from codemap.ingest import CodeIngestor
    >>> from codemap.analyzers import CodeAnalyzer
    >>> 
    >>> # Ingest code
    >>> ingestor = CodeIngestor()
    >>> ingestion = ingestor.ingest("/path/to/project")
    >>> 
    >>> # Analyze code
    >>> analyzer = CodeAnalyzer()
    >>> result = analyzer.analyze(ingestion)
    >>> 
    >>> # Access analysis data
    >>> print(f"Classes: {len(result.all_classes)}")
    >>> print(f"Functions: {len(result.all_functions)}")
    >>> print(f"Dependencies: {len(result.dependencies)}")
"""

from .models import (
    # Core models
    AnalysisResult,
    ModuleInfo,
    ClassInfo,
    FunctionInfo,
    ImportInfo,
    Parameter,
    
    # Enums
    NodeType,
    Visibility,
    
    # Graph models
    CallGraphEdge,
    DependencyEdge,
    
    # API models
    APIEndpoint,
    APIAnalysisResult,
)

from .code_analyzer import CodeAnalyzer
from .ast_analyzer import ASTAnalyzer
from .class_extractor import ClassExtractor
from .function_analyzer import FunctionAnalyzer
from .dependency_mapper import DependencyMapper
from .api_detector import APIDetector

__all__ = [
    # Main API
    'CodeAnalyzer',
    
    # Core models
    'AnalysisResult',
    'ModuleInfo',
    'ClassInfo',
    'FunctionInfo',
    'ImportInfo',
    'Parameter',
    
    # Enums
    'NodeType',
    'Visibility',
    
    # Graph models
    'CallGraphEdge',
    'DependencyEdge',
    
    # API models
    'APIEndpoint',
    'APIAnalysisResult',
    
    # Specialized analyzers (for advanced usage)
    'ASTAnalyzer',
    'ClassExtractor',
    'FunctionAnalyzer',
    'DependencyMapper',
    'APIDetector',
]

__version__ = '0.1.0'