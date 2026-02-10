"""
Mermaid diagram generator.

Generates diagrams in Mermaid syntax:
https://mermaid.js.org/
"""
from typing import List, Set, Dict
from collections import defaultdict

from ..analyzers.models import (
    AnalysisResult, ClassInfo, FunctionInfo,
    DependencyEdge, APIEndpoint, APIAnalysisResult
)
from .models import (
    DiagramConfig, DiagramOutput, DiagramFormat,
    ClassDiagramConfig, DependencyDiagramConfig,
    CallGraphConfig, APIDiagramConfig
)
from .base_generator import BaseDiagramGenerator


class MermaidGenerator(BaseDiagramGenerator):
    """Generates Mermaid diagrams."""
    
    def generate(self, analysis_result: AnalysisResult) -> DiagramOutput:
        """Generate appropriate diagram based on config type."""
        from .models import DiagramType
        
        if self.config.diagram_type == DiagramType.CLASS_DIAGRAM:
            content = self.generate_class_diagram(analysis_result)
        elif self.config.diagram_type == DiagramType.DEPENDENCY_DIAGRAM:
            content = self.generate_dependency_diagram(analysis_result)
        elif self.config.diagram_type == DiagramType.CALL_GRAPH:
            content = self.generate_call_graph(analysis_result)
        else:
            raise ValueError(f"Unsupported diagram type: {self.config.diagram_type}")
        
        return DiagramOutput(
            content=content,
            format=DiagramFormat.MERMAID,
            diagram_type=self.config.diagram_type,
            metadata={'classes': len(analysis_result.all_classes)}
        )
    
    def generate_class_diagram(self, analysis_result: AnalysisResult) -> str:
        """
        Generate a Mermaid class diagram.
        
        Args:
            analysis_result: Analysis results
            
        Returns:
            Mermaid class diagram syntax
        """
        lines = ["classDiagram"]
        
        if self.config.title:
            lines.append(f"    %% {self.config.title}")
        
        lines.append("")
        
        # Filter classes
        classes = self.filter_classes(analysis_result.all_classes)
        
        if not classes:
            lines.append("    %% No classes to display")
            return "\n".join(lines)
        
        # Define classes
        for cls in classes:
            lines.extend(self._generate_class_definition(cls))
            lines.append("")
        
        # Add relationships
        if self.config.show_relationships:
            config = self.config
            if isinstance(config, ClassDiagramConfig):
                lines.extend(self._generate_class_relationships(classes, config))
        
        return "\n".join(lines)
    
    def _generate_class_definition(self, cls: ClassInfo) -> List[str]:
        """Generate Mermaid class definition."""
        lines = []
        
        # Class declaration
        class_line = f"    class {cls.name}"
        
        # Add stereotype if abstract or dataclass
        if cls.is_abstract:
            class_line += " {\n        <<abstract>>"
            needs_close = True
        elif cls.is_dataclass:
            class_line += " {\n        <<dataclass>>"
            needs_close = True
        else:
            class_line += " {"
            needs_close = True
        
        lines.append(class_line)
        
        # Add attributes
        if self.config.show_attributes and cls.attributes:
            for attr in cls.attributes[:10]:  # Limit attributes
                vis_symbol = self.get_visibility_symbol(
                    Visibility.PRIVATE if attr.startswith('_') else Visibility.PUBLIC
                )
                lines.append(f"        {vis_symbol}{attr}")
        
        # Add methods
        if self.config.show_methods:
            methods = [m for m in cls.methods if self.should_include_method(m)]
            for method in methods[:15]:  # Limit methods
                vis_symbol = self.get_visibility_symbol(method.visibility)
                
                # Format method signature
                params = self.format_parameters(method)
                return_type = ""
                if method.return_type and self.config.show_return_types:
                    return_type = f" {self.format_type(method.return_type)}"
                
                method_line = f"        {vis_symbol}{method.name}({params}){return_type}"
                
                # Add special markers
                if method.is_async:
                    method_line += " *async*"
                if method.is_property:
                    method_line += " *property*"
                
                lines.append(method_line)
        
        if needs_close:
            lines.append("    }")
        
        return lines
    
    def _generate_class_relationships(self, classes: List[ClassInfo], 
                                     config: ClassDiagramConfig) -> List[str]:
        """Generate class relationship lines."""
        lines = []
        lines.append("    %% Relationships")
        
        class_names = {cls.name for cls in classes}
        
        for cls in classes:
            # Inheritance
            if config.show_inheritance:
                for base in cls.base_classes:
                    if base in class_names:
                        lines.append(f"    {base} <|-- {cls.name}")
            
            # Composition (has-a relationships from attributes)
            if config.show_composition:
                for attr in cls.attributes:
                    # Check if attribute name matches a class name
                    for other_cls in classes:
                        if other_cls.name.lower() in attr.lower() and other_cls.name != cls.name:
                            lines.append(f"    {cls.name} *-- {other_cls.name}")
                            break
        
        return lines
    
    def generate_dependency_diagram(self, analysis_result: AnalysisResult) -> str:
        """
        Generate a Mermaid dependency diagram (flowchart).
        
        Args:
            analysis_result: Analysis results
            
        Returns:
            Mermaid flowchart syntax
        """
        lines = [f"flowchart {self.config.direction.value}"]
        
        if self.config.title:
            lines.append(f"    %% {self.config.title}")
        
        lines.append("")
        
        # Get unique modules
        modules = set()
        for dep in analysis_result.dependencies:
            modules.add(dep.source)
            modules.add(dep.target)
        
        # Define nodes
        for module in sorted(modules):
            # Sanitize module name for Mermaid
            node_id = module.replace('.', '_').replace('-', '_')
            lines.append(f"    {node_id}[{module}]")
        
        lines.append("")
        
        # Add edges
        for dep in analysis_result.dependencies:
            source_id = dep.source.replace('.', '_').replace('-', '_')
            target_id = dep.target.replace('.', '_').replace('-', '_')
            
            # Use different arrow styles for different import types
            arrow = "-->" if dep.import_type == "import" else "-..->"
            
            lines.append(f"    {source_id} {arrow} {target_id}")
        
        # Highlight circular dependencies if configured
        if isinstance(self.config, DependencyDiagramConfig):
            if self.config.highlight_circular:
                lines.append("")
                lines.append("    %% Circular dependencies")
                # TODO: Add circular dependency highlighting
        
        return "\n".join(lines)
    
    def generate_call_graph(self, analysis_result: AnalysisResult) -> str:
        """
        Generate a Mermaid call graph (flowchart).
        
        Args:
            analysis_result: Analysis results
            
        Returns:
            Mermaid flowchart syntax
        """
        lines = [f"flowchart {self.config.direction.value}"]
        
        if self.config.title:
            lines.append(f"    %% {self.config.title}")
        
        lines.append("")
        
        # Get unique functions from call graph
        functions = set()
        for edge in analysis_result.call_graph:
            functions.add(edge.caller)
            functions.add(edge.callee)
        
        # Define nodes
        for func in sorted(functions):
            # Create readable node ID
            node_id = func.replace('.', '_').replace(':', '_')
            # Shorten display name
            display_name = func.split('.')[-1] if '.' in func else func
            
            lines.append(f"    {node_id}[{display_name}]")
        
        lines.append("")
        
        # Add edges (calls)
        added_edges = set()
        for edge in analysis_result.call_graph:
            caller_id = edge.caller.replace('.', '_').replace(':', '_')
            callee_id = edge.callee.replace('.', '_').replace(':', '_')
            
            edge_key = (caller_id, callee_id)
            if edge_key not in added_edges:
                lines.append(f"    {caller_id} --> {callee_id}")
                added_edges.add(edge_key)
        
        return "\n".join(lines)
    
    def generate_api_diagram(self, api_results: List[APIAnalysisResult]) -> str:
        """
        Generate a Mermaid diagram for API endpoints.
        
        Args:
            api_results: API analysis results
            
        Returns:
            Mermaid flowchart syntax
        """
        lines = [f"flowchart {self.config.direction.value}"]
        
        if self.config.title:
            lines.append(f"    %% {self.config.title}")
        
        lines.append("")
        
        # Combine all endpoints
        all_endpoints = []
        for result in api_results:
            all_endpoints.extend(result.endpoints)
        
        # Group by resource if configured
        if isinstance(self.config, APIDiagramConfig) and self.config.group_by_resource:
            # Extract base resource from paths
            resources = defaultdict(list)
            for endpoint in all_endpoints:
                # Get first path segment as resource
                parts = [p for p in endpoint.path.split('/') if p and not p.startswith('{')]
                resource = parts[0] if parts else 'root'
                resources[resource].append(endpoint)
            
            # Generate subgraphs for each resource
            for resource, endpoints in resources.items():
                lines.append(f"    subgraph {resource}")
                
                for endpoint in endpoints:
                    method = endpoint.method
                    path = endpoint.path
                    func = endpoint.function_name
                    
                    # Create node ID
                    node_id = f"{method}_{func}".replace('.', '_')
                    
                    # Color by method
                    style = self._get_method_color(method)
                    
                    lines.append(f"        {node_id}[\"{method} {path}\"]")
                    if style:
                        lines.append(f"        style {node_id} {style}")
                
                lines.append("    end")
                lines.append("")
        else:
            # Simple list
            for endpoint in all_endpoints:
                method = endpoint.method
                path = endpoint.path
                func = endpoint.function_name
                
                node_id = f"{method}_{func}".replace('.', '_')
                lines.append(f"    {node_id}[\"{method} {path}\"]")
        
        return "\n".join(lines)
    
    def _get_method_color(self, method: str) -> str:
        """Get Mermaid style for HTTP method."""
        colors = {
            'GET': 'fill:#9f9,stroke:#333',
            'POST': 'fill:#99f,stroke:#333',
            'PUT': 'fill:#ff9,stroke:#333',
            'DELETE': 'fill:#f99,stroke:#333',
            'PATCH': 'fill:#f9f,stroke:#333'
        }
        return colors.get(method.upper(), '')


from ..analyzers.models import Visibility