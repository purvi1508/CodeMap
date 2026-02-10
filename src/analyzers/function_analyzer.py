"""
Function analyzer - analyzes functions and builds call graphs.
"""
from typing import Dict, List, Set, Optional, Tuple
from collections import defaultdict
from .models import (
    FunctionInfo, ModuleInfo, AnalysisResult, 
    CallGraphEdge, NodeType
)


class FunctionAnalyzer:
    """Analyzes functions and builds call graphs."""
    
    def __init__(self):
        """Initialize the function analyzer."""
        self.call_graph = {}  # caller -> [callees]
        self.reverse_call_graph = {}  # callee -> [callers]
    
    def extract_from_modules(self, analysis_result: AnalysisResult) -> List[FunctionInfo]:
        """
        Extract all functions from analysis result.
        
        Args:
            analysis_result: The analysis result containing modules
            
        Returns:
            List of all FunctionInfo objects (including methods)
        """
        all_functions = []
        
        for module_info in analysis_result.modules.values():
            all_functions.extend(module_info.get_all_functions())
        
        return all_functions
    
    def build_call_graph(self, analysis_result: AnalysisResult) -> List[CallGraphEdge]:
        """
        Build a call graph showing which functions call which.
        
        Args:
            analysis_result: The analysis result containing modules
            
        Returns:
            List of CallGraphEdge objects
        """
        edges = []
        self.call_graph.clear()
        self.reverse_call_graph.clear()
        
        # Build function name -> info mapping
        function_map = {}
        for module_info in analysis_result.modules.values():
            for func in module_info.get_all_functions():
                full_name = self._get_full_function_name(func, module_info)
                function_map[func.name] = full_name
        
        # Build edges
        for module_info in analysis_result.modules.values():
            for func in module_info.get_all_functions():
                caller = self._get_full_function_name(func, module_info)
                
                for call_name in func.calls:
                    # Try to resolve the full name
                    callee = function_map.get(call_name, call_name)
                    
                    edge = CallGraphEdge(
                        caller=caller,
                        callee=callee,
                        line_number=func.line_number
                    )
                    edges.append(edge)
                    
                    # Update internal graphs
                    if caller not in self.call_graph:
                        self.call_graph[caller] = []
                    self.call_graph[caller].append(callee)
                    
                    if callee not in self.reverse_call_graph:
                        self.reverse_call_graph[callee] = []
                    self.reverse_call_graph[callee].append(caller)
        
        return edges
    
    def get_function_callers(self, function_name: str) -> List[str]:
        """Get all functions that call a specific function."""
        return self.reverse_call_graph.get(function_name, [])
    
    def get_function_callees(self, function_name: str) -> List[str]:
        """Get all functions that a specific function calls."""
        return self.call_graph.get(function_name, [])
    
    def find_recursive_functions(self, functions: List[FunctionInfo]) -> List[str]:
        """Find functions that call themselves (directly recursive)."""
        recursive = []
        
        for func in functions:
            if func.name in func.calls:
                recursive.append(func.name)
        
        return recursive
    
    def find_mutually_recursive_functions(self) -> List[Set[str]]:
        """Find sets of functions that are mutually recursive."""
        visited = set()
        mutual_groups = []
        
        def dfs(func: str, path: Set[str]) -> Optional[Set[str]]:
            if func in path:
                # Found a cycle
                cycle_start = list(path).index(func)
                return set(list(path)[cycle_start:])
            
            if func in visited:
                return None
            
            visited.add(func)
            path.add(func)
            
            for callee in self.call_graph.get(func, []):
                cycle = dfs(callee, path.copy())
                if cycle and len(cycle) > 1:
                    mutual_groups.append(cycle)
            
            return None
        
        for func in self.call_graph.keys():
            if func not in visited:
                dfs(func, set())
        
        # Remove duplicate cycles
        unique_groups = []
        seen = set()
        for group in mutual_groups:
            frozen = frozenset(group)
            if frozen not in seen:
                seen.add(frozen)
                unique_groups.append(group)
        
        return unique_groups
    
    def calculate_function_metrics(self, func: FunctionInfo) -> Dict[str, any]:
        """
        Calculate various metrics for a function.
        
        Args:
            func: The function to analyze
            
        Returns:
            Dictionary with metrics
        """
        return {
            'name': func.name,
            'type': func.node_type.value,
            'parameters': len(func.parameters),
            'lines_of_code': func.end_line_number - func.line_number + 1,
            'complexity': func.complexity,
            'calls_count': len(func.calls),
            'is_async': func.is_async,
            'is_property': func.is_property,
            'has_docstring': func.docstring is not None,
            'has_return_type': func.return_type is not None,
            'decorators': len(func.decorators),
            'visibility': func.visibility.value
        }
    
    def get_most_complex_functions(self, functions: List[FunctionInfo], 
                                   top_n: int = 10) -> List[Tuple[str, int]]:
        """
        Get the most complex functions by cyclomatic complexity.
        
        Args:
            functions: List of functions to analyze
            top_n: Number of top functions to return
            
        Returns:
            List of (function_name, complexity) tuples
        """
        complexities = [(f.name, f.complexity) for f in functions]
        complexities.sort(key=lambda x: x[1], reverse=True)
        return complexities[:top_n]
    
    def get_longest_functions(self, functions: List[FunctionInfo], 
                             top_n: int = 10) -> List[Tuple[str, int]]:
        """
        Get the longest functions by lines of code.
        
        Args:
            functions: List of functions to analyze
            top_n: Number of top functions to return
            
        Returns:
            List of (function_name, loc) tuples
        """
        lengths = []
        for f in functions:
            loc = f.end_line_number - f.line_number + 1
            lengths.append((f.name, loc))
        
        lengths.sort(key=lambda x: x[1], reverse=True)
        return lengths[:top_n]
    
    def get_function_parameter_complexity(self, functions: List[FunctionInfo]) -> Dict[str, int]:
        """
        Analyze parameter complexity across functions.
        
        Returns:
            Dictionary with statistics
        """
        param_counts = [len(f.parameters) for f in functions]
        
        if not param_counts:
            return {
                'total_functions': 0,
                'average_parameters': 0,
                'max_parameters': 0,
                'functions_with_many_params': 0
            }
        
        return {
            'total_functions': len(functions),
            'average_parameters': round(sum(param_counts) / len(param_counts), 2),
            'max_parameters': max(param_counts),
            'functions_with_many_params': len([c for c in param_counts if c > 5])
        }
    
    def identify_pure_functions(self, functions: List[FunctionInfo]) -> List[str]:
        """
        Identify potentially pure functions (no side effects).
        This is a heuristic based on:
        - No global variable modifications
        - No method calls that might have side effects
        - Has return type
        
        Args:
            functions: List of functions to analyze
            
        Returns:
            List of function names that might be pure
        """
        pure = []
        
        for func in functions:
            # Skip methods (harder to determine purity)
            if func.node_type == NodeType.METHOD:
                continue
            
            # Must have return type
            if not func.return_type:
                continue
            
            # Check for suspicious calls
            suspicious_calls = ['print', 'open', 'write', 'read', 'append']
            has_side_effects = any(
                any(sus in call.lower() for sus in suspicious_calls)
                for call in func.calls
            )
            
            if not has_side_effects:
                pure.append(func.name)
        
        return pure
    
    def get_unused_functions(self, functions: List[FunctionInfo]) -> List[str]:
        """
        Find functions that are never called (potential dead code).
        
        Args:
            functions: List of functions to analyze
            
        Returns:
            List of function names that are never called
        """
        unused = []
        
        for func in functions:
            # Skip special methods
            if func.name.startswith('__') and func.name.endswith('__'):
                continue
            
            # Skip if it's called by any function
            if func.name not in self.reverse_call_graph or not self.reverse_call_graph[func.name]:
                unused.append(func.name)
        
        return unused
    
    def get_function_depth(self, function_name: str) -> int:
        """
        Calculate the call depth from a function.
        
        Args:
            function_name: Name of the function
            
        Returns:
            Maximum depth of function calls
        """
        def calculate_depth(func: str, visited: Set[str]) -> int:
            if func not in self.call_graph or func in visited:
                return 0
            
            visited.add(func)
            max_depth = 0
            
            for callee in self.call_graph[func]:
                depth = calculate_depth(callee, visited.copy())
                max_depth = max(max_depth, depth)
            
            return max_depth + 1
        
        return calculate_depth(function_name, set())
    
    def analyze_async_usage(self, functions: List[FunctionInfo]) -> Dict[str, any]:
        """
        Analyze async function usage.
        
        Args:
            functions: List of functions to analyze
            
        Returns:
            Dictionary with async statistics
        """
        async_funcs = [f for f in functions if f.is_async]
        
        return {
            'total_functions': len(functions),
            'async_functions': len(async_funcs),
            'async_percentage': round(len(async_funcs) / len(functions) * 100, 2) if functions else 0,
            'async_function_names': [f.name for f in async_funcs]
        }
    
    def _get_full_function_name(self, func: FunctionInfo, module: ModuleInfo) -> str:
        """Get the fully qualified function name."""
        # For methods, we would need class context
        # For now, use module.function format
        return f"{module.name}.{func.name}"