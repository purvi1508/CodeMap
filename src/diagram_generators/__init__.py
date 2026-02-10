"""
Diagram generators module for CodeMap.

This module provides diagram generation capabilities for:
- Class diagrams
- Dependency diagrams
- Call graphs
- API documentation diagrams

Supports multiple output formats:
- Mermaid
- PlantUML
- Graphviz (future)

Usage:
    >>> from src.ingest import CodeIngestor
    >>> from src.analyzers import CodeAnalyzer
    >>> from src.diagram_generators import DiagramGenerator
    >>> 
    >>> # Ingest and analyze
    >>> ingestor = CodeIngestor()
    >>> ingestion = ingestor.ingest("/path/to/project")
    >>> 
    >>> analyzer = CodeAnalyzer()
    >>> result = analyzer.analyze(ingestion)
    >>> 
    >>> # Generate diagrams
    >>> generator = DiagramGenerator()
    >>> class_diagram = generator.generate_class_diagram(result)
    >>> print(class_diagram.content)
    >>> 
    >>> # Generate all diagrams
    >>> diagrams = generator.generate_all(result)
    >>> diagrams.save_all("./output")
"""

from .models import (
    # Configuration models
    DiagramConfig,
    ClassDiagramConfig,
    DependencyDiagramConfig,
    CallGraphConfig,
    APIDiagramConfig,
    
    # Output models
    DiagramOutput,
    MultiDiagramOutput,
    
    # Enums
    DiagramType,
    DiagramFormat,
    LayoutDirection,
)

from .diagram_generator import DiagramGenerator
from .mermaid_generator import MermaidGenerator
from .plantuml_generator import PlantUMLGenerator
from .base_generator import BaseDiagramGenerator

__all__ = [
    # Main API
    'DiagramGenerator',
    
    # Configuration models
    'DiagramConfig',
    'ClassDiagramConfig',
    'DependencyDiagramConfig',
    'CallGraphConfig',
    'APIDiagramConfig',
    
    # Output models
    'DiagramOutput',
    'MultiDiagramOutput',
    
    # Enums
    'DiagramType',
    'DiagramFormat',
    'LayoutDirection',
    
    # Specialized generators (for advanced usage)
    'MermaidGenerator',
    'PlantUMLGenerator',
    'BaseDiagramGenerator',
]

__version__ = '0.1.0'