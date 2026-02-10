"""
Main code analyzer - orchestrates all analysis components.
"""
from pathlib import Path
from typing import Optional, List

from ..ingest import CodebaseIngestion, FileInfo
from .models import AnalysisResult, ModuleInfo, APIAnalysisResult
from .ast_analyzer import ASTAnalyzer
from .class_extractor import ClassExtractor
from .function_analyzer import FunctionAnalyzer
from .dependency_mapper import DependencyMapper
from .api_detector import APIDetector


class CodeAnalyzer:
    """
    Main analyzer that coordinates all analysis components.
    
    This is the primary entry point for code analysis.
    """
    
    def __init__(self):
        """Initialize the code analyzer."""
        self.ast_analyzer = ASTAnalyzer()
        self.class_extractor = ClassExtractor()
        self.function_analyzer = FunctionAnalyzer()
        self.dependency_mapper = DependencyMapper()
        self.api_detector = APIDetector()
    
    def analyze(self, ingestion: CodebaseIngestion) -> AnalysisResult:
        """
        Perform complete analysis on an ingested codebase.
        
        Args:
            ingestion: CodebaseIngestion result from the ingest module
            
        Returns:
            AnalysisResult with all analysis data
        """
        result = AnalysisResult()
        
        # Step 1: Analyze each Python file
        for file_info in ingestion.get_python_files():
            module_info = self._analyze_file(file_info)
            
            if module_info:
                result.modules[str(file_info.path)] = module_info
            else:
                result.warnings.append(f"Could not analyze: {file_info.path}")
        
        # Step 2: Extract all classes
        result.all_classes = self.class_extractor.extract_from_modules(result)
        
        # Step 3: Extract all functions
        result.all_functions = self.function_analyzer.extract_from_modules(result)
        
        # Step 4: Build call graph
        result.call_graph = self.function_analyzer.build_call_graph(result)
        
        # Step 5: Build dependency graph
        result.dependencies = self.dependency_mapper.build_dependency_graph(result)
        
        return result
    
    def analyze_with_api(self, ingestion: CodebaseIngestion) -> tuple[AnalysisResult, List[APIAnalysisResult]]:
        """
        Perform analysis including API endpoint detection.
        
        Args:
            ingestion: CodebaseIngestion result
            
        Returns:
            Tuple of (AnalysisResult, list of APIAnalysisResult)
        """
        # Regular analysis
        result = self.analyze(ingestion)
        
        # API analysis
        api_results = []
        for file_info in ingestion.get_python_files():
            api_result = self.api_detector.analyze_file(file_info.path, file_info.content)
            if api_result:
                api_results.append(api_result)
        
        return result, api_results
    
    def _analyze_file(self, file_info: FileInfo) -> Optional[ModuleInfo]:
        """
        Analyze a single Python file.
        
        Args:
            file_info: FileInfo from ingestion
            
        Returns:
            ModuleInfo or None if analysis fails
        """
        try:
            return self.ast_analyzer.analyze_file(file_info.path, file_info.content)
        except Exception as e:
            return None
    
    def get_analysis_summary(self, result: AnalysisResult) -> dict:
        """
        Get a high-level summary of the analysis.
        
        Args:
            result: Analysis result
            
        Returns:
            Dictionary with summary statistics
        """
        return {
            'modules': len(result.modules),
            'classes': len(result.all_classes),
            'functions': len(result.all_functions),
            'call_graph_edges': len(result.call_graph),
            'dependencies': len(result.dependencies),
            'circular_dependencies': len(self.dependency_mapper.find_circular_dependencies()),
            'errors': len(result.errors),
            'warnings': len(result.warnings)
        }
    
    def get_complexity_report(self, result: AnalysisResult) -> dict:
        """
        Generate a complexity report.
        
        Args:
            result: Analysis result
            
        Returns:
            Dictionary with complexity metrics
        """
        # Most complex functions
        complex_funcs = self.function_analyzer.get_most_complex_functions(
            result.all_functions, top_n=10
        )
        
        # Longest functions
        long_funcs = self.function_analyzer.get_longest_functions(
            result.all_functions, top_n=10
        )
        
        # Class complexity
        class_metrics = [
            self.class_extractor.analyze_class_complexity(cls)
            for cls in result.all_classes
        ]
        
        # Sort by LOC
        class_metrics.sort(key=lambda x: x['lines_of_code'], reverse=True)
        
        return {
            'most_complex_functions': complex_funcs,
            'longest_functions': long_funcs,
            'largest_classes': class_metrics[:10],
            'parameter_complexity': self.function_analyzer.get_function_parameter_complexity(
                result.all_functions
            )
        }
    
    def get_dependency_report(self, result: AnalysisResult) -> dict:
        """
        Generate a dependency report.
        
        Args:
            result: Analysis result
            
        Returns:
            Dictionary with dependency analysis
        """
        circular = self.dependency_mapper.find_circular_dependencies()
        coupling = self.dependency_mapper.calculate_coupling_metrics()
        highly_coupled = self.dependency_mapper.identify_highly_coupled_modules()
        layers = self.dependency_mapper.get_dependency_layers()
        
        return {
            'circular_dependencies': circular,
            'coupling_metrics': coupling,
            'highly_coupled_modules': highly_coupled,
            'dependency_layers': layers,
            'god_modules': self.dependency_mapper.find_god_modules(),
            'leaf_modules': self.dependency_mapper.find_leaf_modules(),
            'root_modules': self.dependency_mapper.find_root_modules()
        }
    
    def get_class_report(self, result: AnalysisResult) -> dict:
        """
        Generate a class hierarchy and pattern report.
        
        Args:
            result: Analysis result
            
        Returns:
            Dictionary with class analysis
        """
        patterns = self.class_extractor.detect_design_patterns(result.all_classes)
        overrides = self.class_extractor.get_method_override_analysis(result.all_classes)
        relationships = self.class_extractor.get_class_relationships(result.all_classes)
        
        return {
            'total_classes': len(result.all_classes),
            'abstract_classes': [cls.name for cls in self.class_extractor.get_abstract_classes(result.all_classes)],
            'dataclasses': [cls.name for cls in self.class_extractor.get_dataclasses(result.all_classes)],
            'design_patterns': patterns,
            'method_overrides': overrides,
            'class_relationships': relationships
        }
    
    def get_function_report(self, result: AnalysisResult) -> dict:
        """
        Generate a function analysis report.
        
        Args:
            result: Analysis result
            
        Returns:
            Dictionary with function analysis
        """
        recursive = self.function_analyzer.find_recursive_functions(result.all_functions)
        mutual = self.function_analyzer.find_mutually_recursive_functions()
        pure = self.function_analyzer.identify_pure_functions(result.all_functions)
        unused = self.function_analyzer.get_unused_functions(result.all_functions)
        async_stats = self.function_analyzer.analyze_async_usage(result.all_functions)
        
        return {
            'total_functions': len(result.all_functions),
            'recursive_functions': recursive,
            'mutually_recursive_groups': mutual,
            'potentially_pure_functions': pure,
            'unused_functions': unused,
            'async_statistics': async_stats
        }
    
    def get_api_report(self, api_results: List[APIAnalysisResult]) -> dict:
        """
        Generate an API analysis report.
        
        Args:
            api_results: List of API analysis results
            
        Returns:
            Dictionary with API analysis
        """
        if not api_results:
            return {'frameworks_detected': None}
        
        frameworks = set(r.framework for r in api_results)
        all_endpoints = []
        for result in api_results:
            all_endpoints.extend(result.endpoints)
        
        # Combine all endpoints
        combined = APIAnalysisResult(
            framework=', '.join(frameworks),
            endpoints=all_endpoints
        )
        
        summary = self.api_detector.generate_api_summary(combined)
        patterns = self.api_detector.detect_rest_patterns(combined)
        violations = self.api_detector.check_rest_conventions(combined)
        
        return {
            'frameworks_detected': list(frameworks),
            'summary': summary,
            'rest_patterns': patterns,
            'rest_violations': violations,
            'endpoints_by_method': combined.get_endpoint_count()
        }
    
    def generate_full_report(self, ingestion: CodebaseIngestion) -> dict:
        """
        Generate a comprehensive analysis report.
        
        Args:
            ingestion: CodebaseIngestion result
            
        Returns:
            Complete analysis report
        """
        result, api_results = self.analyze_with_api(ingestion)
        
        return {
            'summary': self.get_analysis_summary(result),
            'complexity': self.get_complexity_report(result),
            'dependencies': self.get_dependency_report(result),
            'classes': self.get_class_report(result),
            'functions': self.get_function_report(result),
            'api': self.get_api_report(api_results)
        }