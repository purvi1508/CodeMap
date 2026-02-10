"""
PlantUML diagram generator.

Generates diagrams in PlantUML syntax:
https://plantuml.com/
"""
from typing import List, Set, Dict
from collections import defaultdict

from ..analyzers.models import (
    AnalysisResult, ClassInfo, FunctionInfo,
    APIAnalysisResult, Visibility
)
from .models import (
    DiagramConfig, DiagramOutput, DiagramFormat,
    ClassDiagramConfig, DependencyDiagramConfig
)
from .base_generator import BaseDiagramGenerator


class PlantUMLGenerator(BaseDiagramGenerator):
    """Generates PlantUML diagrams."""
    
    def generate(self, analysis_result: AnalysisResult) -> DiagramOutput:
        """Generate appropriate diagram based on config type."""
        from .models import DiagramType
        
        if self.config.diagram_type == DiagramType.CLASS_DIAGRAM:
            content = self.generate_class_diagram(analysis_result)
        elif self.config.diagram_type == DiagramType.DEPENDENCY_DIAGRAM:
            content = self.generate_dependency_diagram(analysis_result)
        elif self.config.diagram_type == DiagramType.COMPONENT_DIAGRAM:
            content = self.generate_component_diagram(analysis_result)
        else:
            raise ValueError(f"Unsupported diagram type: {self.config.diagram_type}")
        
        return DiagramOutput(
            content=content,
            format=DiagramFormat.PLANTUML,
            diagram_type=self.config.diagram_type
        )
    
    def generate_class_diagram(self, analysis_result: AnalysisResult) -> str:
        """
        Generate a PlantUML class diagram.
        
        Args:
            analysis_result: Analysis results
            
        Returns:
            PlantUML syntax
        """
        lines = ["@startuml"]
        
        if self.config.title:
            lines.append(f"title {self.config.title}")
        
        lines.append("")
        
        # Set direction
        direction_map = {
            "TB": "top to bottom direction",
            "LR": "left to right direction"
        }
        if self.config.direction.value in direction_map:
            lines.append(direction_map[self.config.direction.value])
            lines.append("")
        
        # Filter classes
        classes = self.filter_classes(analysis_result.all_classes)
        
        if not classes:
            lines.append("note \"No classes to display\" as N1")
            lines.append("@enduml")
            return "\n".join(lines)
        
        # Group by module if configured
        if self.config.group_by_module:
            modules = defaultdict(list)
            for cls in classes:
                # Get module from first module info that contains this class
                module_name = "default"
                for module_path, module_info in analysis_result.modules.items():
                    if any(c.name == cls.name for c in module_info.classes):
                        module_name = module_info.name
                        break
                modules[module_name].append(cls)
            
            # Generate packages
            for module_name, module_classes in modules.items():
                lines.append(f"package {module_name} {{")
                for cls in module_classes:
                    lines.extend(self._generate_class_definition(cls))
                lines.append("}")
                lines.append("")
        else:
            # Define classes
            for cls in classes:
                lines.extend(self._generate_class_definition(cls))
                lines.append("")
        
        # Add relationships
        if self.config.show_relationships:
            config = self.config
            if isinstance(config, ClassDiagramConfig):
                lines.extend(self._generate_class_relationships(classes, config))
        
        lines.append("@enduml")
        return "\n".join(lines)
    
    def _generate_class_definition(self, cls: ClassInfo) -> List[str]:
        """Generate PlantUML class definition."""
        lines = []
        
        # Class type
        if cls.is_abstract:
            class_type = "abstract class"
        else:
            class_type = "class"
        
        lines.append(f"{class_type} {cls.name} {{")
        
        # Add stereotype
        if cls.is_dataclass:
            lines.append("    <<dataclass>>")
        
        # Add attributes
        if self.config.show_attributes and cls.attributes:
            for attr in cls.attributes[:15]:  # Limit attributes
                vis_symbol = self.get_visibility_symbol(
                    Visibility.PRIVATE if attr.startswith('_') else Visibility.PUBLIC
                )
                lines.append(f"    {vis_symbol} {attr}")
            
            if cls.attributes and cls.methods:
                lines.append("    ..")
        
        # Add methods
        if self.config.show_methods:
            methods = [m for m in cls.methods if self.should_include_method(m)]
            for method in methods[:20]:  # Limit methods
                vis_symbol = self.get_visibility_symbol(method.visibility)
                
                # Format method signature
                params = self.format_parameters(method)
                return_type = ""
                if method.return_type and self.config.show_return_types:
                    return_type = f" : {self.format_type(method.return_type)}"
                
                method_line = f"    {vis_symbol} {method.name}({params}){return_type}"
                
                # Add special markers
                if hasattr(method, 'is_abstract') and method.is_abstract:
                    method_line = f"    {{abstract}} {method_line}"
                if method.is_async:
                    method_line += " <<async>>"
                
                lines.append(method_line)
        
        lines.append("}")
        
        return lines
    
    def _generate_class_relationships(self, classes: List[ClassInfo],
                                     config: ClassDiagramConfig) -> List[str]:
        """Generate PlantUML relationship lines."""
        lines = []
        lines.append("' Relationships")
        
        class_names = {cls.name for cls in classes}
        
        for cls in classes:
            # Inheritance
            if config.show_inheritance:
                for base in cls.base_classes:
                    if base in class_names:
                        lines.append(f"{base} <|-- {cls.name}")
            
            # Composition (strong ownership)
            if config.show_composition:
                for attr in cls.attributes:
                    for other_cls in classes:
                        if other_cls.name.lower() in attr.lower() and other_cls.name != cls.name:
                            lines.append(f"{cls.name} *-- {other_cls.name}")
                            break
        
        return lines
    
    def generate_dependency_diagram(self, analysis_result: AnalysisResult) -> str:
        """
        Generate a PlantUML component diagram for dependencies.
        
        Args:
            analysis_result: Analysis results
            
        Returns:
            PlantUML syntax
        """
        lines = ["@startuml"]
        
        if self.config.title:
            lines.append(f"title {self.config.title}")
        
        lines.append("")
        lines.append("left to right direction")
        lines.append("")
        
        # Get unique modules
        modules = set()
        for dep in analysis_result.dependencies:
            modules.add(dep.source)
            modules.add(dep.target)
        
        # Define components
        for module in sorted(modules):
            lines.append(f"component [{module}] as {module.replace('.', '_')}")
        
        lines.append("")
        
        # Add dependencies
        for dep in analysis_result.dependencies:
            source = dep.source.replace('.', '_')
            target = dep.target.replace('.', '_')
            
            # Use different arrow types
            arrow = "-->" if dep.import_type == "import" else "..>"
            
            lines.append(f"{source} {arrow} {target}")
        
        lines.append("@enduml")
        return "\n".join(lines)
    
    def generate_component_diagram(self, analysis_result: AnalysisResult) -> str:
        """
        Generate a PlantUML component diagram.
        
        Args:
            analysis_result: Analysis results
            
        Returns:
            PlantUML syntax
        """
        lines = ["@startuml"]
        
        if self.config.title:
            lines.append(f"title {self.config.title}")
        
        lines.append("")
        
        # Group modules by package
        packages = defaultdict(list)
        for module_path, module_info in analysis_result.modules.items():
            # Get package name (parent directory)
            parts = module_info.name.split('.')
            package = parts[0] if len(parts) > 1 else "default"
            packages[package].append(module_info.name)
        
        # Generate packages
        for package_name, modules in packages.items():
            lines.append(f"package {package_name} {{")
            for module in modules:
                lines.append(f"    component [{module}]")
            lines.append("}")
            lines.append("")
        
        # Add dependencies
        for dep in analysis_result.dependencies:
            lines.append(f"[{dep.source}] --> [{dep.target}]")
        
        lines.append("@enduml")
        return "\n".join(lines)
    
    def generate_sequence_diagram(self, call_graph_edges: List, 
                                  entry_point: str) -> str:
        """
        Generate a PlantUML sequence diagram from call graph.
        
        Args:
            call_graph_edges: Call graph edges
            entry_point: Starting function
            
        Returns:
            PlantUML syntax
        """
        lines = ["@startuml"]
        
        if self.config.title:
            lines.append(f"title {self.config.title}")
        
        lines.append("")
        
        # Track participants
        participants = set()
        
        # Build call sequence
        for edge in call_graph_edges:
            if edge.caller == entry_point or entry_point in edge.caller:
                caller = edge.caller.split('.')[-1]
                callee = edge.callee.split('.')[-1]
                
                participants.add(caller)
                participants.add(callee)
                
                lines.append(f"{caller} -> {callee}: call")
        
        lines.append("@enduml")
        return "\n".join(lines)