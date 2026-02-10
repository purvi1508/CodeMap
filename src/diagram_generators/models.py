"""
Data models for diagram generation configuration.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Set, Dict, Any
from enum import Enum


class DiagramType(Enum):
    """Types of diagrams that can be generated."""
    CLASS_DIAGRAM = "class"
    SEQUENCE_DIAGRAM = "sequence"
    DEPENDENCY_DIAGRAM = "dependency"
    CALL_GRAPH = "call_graph"
    API_DIAGRAM = "api"
    COMPONENT_DIAGRAM = "component"
    PACKAGE_DIAGRAM = "package"


class DiagramFormat(Enum):
    """Output formats for diagrams."""
    MERMAID = "mermaid"
    PLANTUML = "plantuml"
    GRAPHVIZ = "graphviz"
    D2 = "d2"


class LayoutDirection(Enum):
    """Layout direction for diagrams."""
    TOP_TO_BOTTOM = "TB"
    BOTTOM_TO_TOP = "BT"
    LEFT_TO_RIGHT = "LR"
    RIGHT_TO_LEFT = "RL"


@dataclass
class DiagramConfig:
    """Configuration for diagram generation."""
    format: DiagramFormat = DiagramFormat.MERMAID
    diagram_type: DiagramType = DiagramType.CLASS_DIAGRAM
    title: Optional[str] = None
    direction: LayoutDirection = LayoutDirection.TOP_TO_BOTTOM
    
    # Filtering options
    include_private: bool = False
    include_protected: bool = True
    include_magic_methods: bool = False
    max_depth: int = 5
    
    # Display options
    show_attributes: bool = True
    show_methods: bool = True
    show_parameters: bool = True
    show_return_types: bool = True
    show_relationships: bool = True
    show_cardinality: bool = False
    
    # Grouping options
    group_by_module: bool = False
    group_by_package: bool = False
    
    # Filtering by name patterns
    include_patterns: List[str] = field(default_factory=list)
    exclude_patterns: List[str] = field(default_factory=list)
    
    # Style options
    theme: str = "default"
    colors: Dict[str, str] = field(default_factory=dict)
    
    # Size limits
    max_classes: Optional[int] = None
    max_functions: Optional[int] = None
    
    def should_include(self, name: str) -> bool:
        """Check if an element should be included based on patterns."""
        # Check exclude patterns first
        if self.exclude_patterns:
            for pattern in self.exclude_patterns:
                if pattern in name:
                    return False
        
        # If include patterns exist, must match at least one
        if self.include_patterns:
            return any(pattern in name for pattern in self.include_patterns)
        
        return True


@dataclass
class ClassDiagramConfig(DiagramConfig):
    """Configuration specific to class diagrams."""
    show_inheritance: bool = True
    show_composition: bool = True
    show_aggregation: bool = True
    show_dependencies: bool = True
    show_inner_classes: bool = False
    collapse_inherited_methods: bool = False
    
    def __post_init__(self):
        from .models import DiagramType
        self.diagram_type = DiagramType.CLASS_DIAGRAM


@dataclass
class DependencyDiagramConfig(DiagramConfig):
    """Configuration specific to dependency diagrams."""
    show_external_deps: bool = False
    highlight_circular: bool = True
    show_layer_numbers: bool = True
    cluster_by_layer: bool = True
    
    def __post_init__(self):
        self.diagram_type = DiagramType.DEPENDENCY_DIAGRAM


@dataclass
class CallGraphConfig(DiagramConfig):
    """Configuration specific to call graphs."""
    max_call_depth: int = 3
    show_call_counts: bool = False
    highlight_recursive: bool = True
    entry_points: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        self.diagram_type = DiagramType.CALL_GRAPH


@dataclass
class APIDiagramConfig(DiagramConfig):
    """Configuration specific to API diagrams."""
    group_by_resource: bool = True
    show_methods: bool = True
    show_parameters: bool = True
    show_status_codes: bool = False
    color_by_method: bool = True
    
    def __post_init__(self):
        self.diagram_type = DiagramType.API_DIAGRAM


@dataclass
class DiagramOutput:
    """Generated diagram output."""
    content: str
    format: DiagramFormat
    diagram_type: DiagramType
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def save(self, filepath: str):
        """Save diagram to file."""
        from pathlib import Path
        Path(filepath).write_text(self.content)
    
    def get_file_extension(self) -> str:
        """Get appropriate file extension for the format."""
        extensions = {
            DiagramFormat.MERMAID: ".mmd",
            DiagramFormat.PLANTUML: ".puml",
            DiagramFormat.GRAPHVIZ: ".dot",
            DiagramFormat.D2: ".d2"
        }
        return extensions.get(self.format, ".txt")


@dataclass
class MultiDiagramOutput:
    """Collection of multiple diagrams."""
    diagrams: List[DiagramOutput] = field(default_factory=list)
    
    def add_diagram(self, diagram: DiagramOutput):
        """Add a diagram to the collection."""
        self.diagrams.append(diagram)
    
    def get_by_type(self, diagram_type: DiagramType) -> List[DiagramOutput]:
        """Get all diagrams of a specific type."""
        return [d for d in self.diagrams if d.diagram_type == diagram_type]
    
    def get_by_format(self, format: DiagramFormat) -> List[DiagramOutput]:
        """Get all diagrams of a specific format."""
        return [d for d in self.diagrams if d.format == format]
    
    def save_all(self, output_dir: str):
        """Save all diagrams to a directory."""
        from pathlib import Path
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        for i, diagram in enumerate(self.diagrams):
            filename = f"{diagram.diagram_type.value}_{i}{diagram.get_file_extension()}"
            diagram.save(output_path / filename)