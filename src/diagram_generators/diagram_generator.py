"""
Main diagram generator - orchestrates all diagram generation.
"""
from typing import List, Optional, Union
from pathlib import Path

from ..analyzers.models import AnalysisResult, APIAnalysisResult
from .models import (
    DiagramConfig, DiagramOutput, MultiDiagramOutput,
    DiagramType, DiagramFormat, ClassDiagramConfig,
    DependencyDiagramConfig, CallGraphConfig, APIDiagramConfig
)
from .mermaid_generator import MermaidGenerator
from .plantuml_generator import PlantUMLGenerator


class DiagramGenerator:
    """
    Main diagram generator that orchestrates all diagram types.
    
    This is the primary entry point for diagram generation.
    """
    
    def __init__(self):
        """Initialize the diagram generator."""
        self.generators = {}
    
    def generate(self, analysis_result: AnalysisResult,
                config: DiagramConfig) -> DiagramOutput:
        """
        Generate a single diagram.
        
        Args:
            analysis_result: Analysis results
            config: Diagram configuration
            
        Returns:
            DiagramOutput
        """
        generator = self._get_generator(config)
        return generator.generate(analysis_result)
    
    def generate_class_diagram(self, analysis_result: AnalysisResult,
                              format: DiagramFormat = DiagramFormat.MERMAID,
                              **kwargs) -> DiagramOutput:
        """
        Generate a class diagram.
        
        Args:
            analysis_result: Analysis results
            format: Output format
            **kwargs: Additional configuration options
            
        Returns:
            DiagramOutput
        """
        config = ClassDiagramConfig(
            format=format,
            **kwargs
        )
        return self.generate(analysis_result, config)
    
    def generate_dependency_diagram(self, analysis_result: AnalysisResult,
                                   format: DiagramFormat = DiagramFormat.MERMAID,
                                   **kwargs) -> DiagramOutput:
        """
        Generate a dependency diagram.
        
        Args:
            analysis_result: Analysis results
            format: Output format
            **kwargs: Additional configuration options
            
        Returns:
            DiagramOutput
        """
        config = DependencyDiagramConfig(
            format=format,
            **kwargs
        )
        return self.generate(analysis_result, config)
    
    def generate_call_graph(self, analysis_result: AnalysisResult,
                           format: DiagramFormat = DiagramFormat.MERMAID,
                           **kwargs) -> DiagramOutput:
        """
        Generate a call graph diagram.
        
        Args:
            analysis_result: Analysis results
            format: Output format
            **kwargs: Additional configuration options
            
        Returns:
            DiagramOutput
        """
        config = CallGraphConfig(
            format=format,
            **kwargs
        )
        return self.generate(analysis_result, config)
    
    def generate_api_diagram(self, api_results: List[APIAnalysisResult],
                            format: DiagramFormat = DiagramFormat.MERMAID,
                            **kwargs) -> DiagramOutput:
        """
        Generate an API diagram.
        
        Args:
            api_results: API analysis results
            format: Output format
            **kwargs: Additional configuration options
            
        Returns:
            DiagramOutput
        """
        config = APIDiagramConfig(
            format=format,
            **kwargs
        )
        
        generator = self._get_generator(config)
        
        if isinstance(generator, MermaidGenerator):
            content = generator.generate_api_diagram(api_results)
            return DiagramOutput(
                content=content,
                format=format,
                diagram_type=DiagramType.API_DIAGRAM
            )
        else:
            raise NotImplementedError(f"API diagrams not supported for {format}")
    
    def generate_all(self, analysis_result: AnalysisResult,
                    api_results: Optional[List[APIAnalysisResult]] = None,
                    formats: List[DiagramFormat] = None) -> MultiDiagramOutput:
        """
        Generate all diagram types.
        
        Args:
            analysis_result: Analysis results
            api_results: Optional API analysis results
            formats: Formats to generate (default: [MERMAID])
            
        Returns:
            MultiDiagramOutput with all diagrams
        """
        if formats is None:
            formats = [DiagramFormat.MERMAID]
        
        output = MultiDiagramOutput()
        
        for format in formats:
            # Class diagram
            try:
                diagram = self.generate_class_diagram(
                    analysis_result,
                    format=format,
                    title="Class Diagram"
                )
                output.add_diagram(diagram)
            except Exception as e:
                print(f"Error generating class diagram: {e}")
            
            # Dependency diagram
            try:
                diagram = self.generate_dependency_diagram(
                    analysis_result,
                    format=format,
                    title="Module Dependencies"
                )
                output.add_diagram(diagram)
            except Exception as e:
                print(f"Error generating dependency diagram: {e}")
            
            # Call graph
            try:
                diagram = self.generate_call_graph(
                    analysis_result,
                    format=format,
                    title="Function Call Graph"
                )
                output.add_diagram(diagram)
            except Exception as e:
                print(f"Error generating call graph: {e}")
            
            # API diagram (if available)
            if api_results:
                try:
                    diagram = self.generate_api_diagram(
                        api_results,
                        format=format,
                        title="API Endpoints"
                    )
                    output.add_diagram(diagram)
                except Exception as e:
                    print(f"Error generating API diagram: {e}")
        
        return output
    
    def generate_architecture_overview(self, analysis_result: AnalysisResult,
                                       format: DiagramFormat = DiagramFormat.MERMAID) -> str:
        """
        Generate a high-level architecture overview combining multiple views.
        
        Args:
            analysis_result: Analysis results
            format: Output format
            
        Returns:
            Combined diagram content
        """
        sections = []
        
        sections.append("# Architecture Overview")
        sections.append("")
        
        # Summary statistics
        sections.append("## Summary")
        sections.append(f"- Modules: {len(analysis_result.modules)}")
        sections.append(f"- Classes: {len(analysis_result.all_classes)}")
        sections.append(f"- Functions: {len(analysis_result.all_functions)}")
        sections.append(f"- Dependencies: {len(analysis_result.dependencies)}")
        sections.append("")
        
        # Class diagram
        sections.append("## Class Structure")
        sections.append("")
        class_diagram = self.generate_class_diagram(analysis_result, format=format)
        if format == DiagramFormat.MERMAID:
            sections.append("```mermaid")
            sections.append(class_diagram.content)
            sections.append("```")
        else:
            sections.append(class_diagram.content)
        sections.append("")
        
        # Dependency diagram
        sections.append("## Module Dependencies")
        sections.append("")
        dep_diagram = self.generate_dependency_diagram(analysis_result, format=format)
        if format == DiagramFormat.MERMAID:
            sections.append("```mermaid")
            sections.append(dep_diagram.content)
            sections.append("```")
        else:
            sections.append(dep_diagram.content)
        sections.append("")
        
        return "\n".join(sections)
    
    def save_diagram(self, diagram: DiagramOutput, filepath: Union[str, Path]):
        """
        Save a diagram to a file.
        
        Args:
            diagram: Diagram to save
            filepath: Output file path
        """
        diagram.save(str(filepath))
    
    def save_all_diagrams(self, diagrams: MultiDiagramOutput,
                         output_dir: Union[str, Path],
                         prefix: str = ""):
        """
        Save all diagrams to a directory.
        
        Args:
            diagrams: Diagrams to save
            output_dir: Output directory
            prefix: Optional filename prefix
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        for i, diagram in enumerate(diagrams.diagrams):
            filename = f"{prefix}{diagram.diagram_type.value}_{i}{diagram.get_file_extension()}"
            self.save_diagram(diagram, output_path / filename)
    
    def _get_generator(self, config: DiagramConfig):
        """Get the appropriate generator for a format."""
        if config.format == DiagramFormat.MERMAID:
            return MermaidGenerator(config)
        elif config.format == DiagramFormat.PLANTUML:
            return PlantUMLGenerator(config)
        else:
            raise ValueError(f"Unsupported format: {config.format}")
    
    def quick_generate(self, analysis_result: AnalysisResult,
                      output_dir: str = "./diagrams",
                      formats: List[str] = None) -> MultiDiagramOutput:
        """
        Quick generation of common diagrams.
        
        Args:
            analysis_result: Analysis results
            output_dir: Output directory
            formats: List of format names (e.g., ['mermaid', 'plantuml'])
            
        Returns:
            MultiDiagramOutput
        """
        if formats is None:
            formats = ['mermaid']
        
        # Convert string formats to DiagramFormat enums
        format_enums = []
        for fmt in formats:
            if fmt.lower() == 'mermaid':
                format_enums.append(DiagramFormat.MERMAID)
            elif fmt.lower() == 'plantuml':
                format_enums.append(DiagramFormat.PLANTUML)
        
        # Generate all diagrams
        diagrams = self.generate_all(analysis_result, formats=format_enums)
        
        # Save to directory
        self.save_all_diagrams(diagrams, output_dir)
        
        return diagrams