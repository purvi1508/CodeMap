"""
Dependency mapper - analyzes dependencies between modules.
"""
from typing import Dict, List, Set, Tuple, Optional
from pathlib import Path
from collections import defaultdict

from .models import ModuleInfo, AnalysisResult, DependencyEdge, ImportInfo


class DependencyMapper:
    """Maps and analyzes dependencies between modules."""
    
    def __init__(self):
        """Initialize the dependency mapper."""
        self.dependency_graph = {}  # module -> [dependencies]
        self.reverse_dependency_graph = {}  # module -> [dependents]
    
    def build_dependency_graph(self, analysis_result: AnalysisResult) -> List[DependencyEdge]:
        """
        Build a dependency graph from the analysis result.
        
        Args:
            analysis_result: The analysis result containing modules
            
        Returns:
            List of DependencyEdge objects
        """
        edges = []
        self.dependency_graph.clear()
        self.reverse_dependency_graph.clear()
        
        module_names = {Path(path).stem for path in analysis_result.modules.keys()}
        
        for module_path, module_info in analysis_result.modules.items():
            source_name = module_info.name
            
            if source_name not in self.dependency_graph:
                self.dependency_graph[source_name] = []
            
            for import_info in module_info.imports:
                target_module = self._extract_base_module(import_info.module)
                
                # Only track internal dependencies (within the codebase)
                if target_module in module_names:
                    edge = DependencyEdge(
                        source=source_name,
                        target=target_module,
                        import_type="from_import" if import_info.is_from_import else "import",
                        names=import_info.names
                    )
                    edges.append(edge)
                    
                    # Update internal graphs
                    self.dependency_graph[source_name].append(target_module)
                    
                    if target_module not in self.reverse_dependency_graph:
                        self.reverse_dependency_graph[target_module] = []
                    self.reverse_dependency_graph[target_module].append(source_name)
        
        return edges
    
    def get_module_dependencies(self, module_name: str) -> List[str]:
        """Get all modules that a module depends on."""
        return self.dependency_graph.get(module_name, [])
    
    def get_module_dependents(self, module_name: str) -> List[str]:
        """Get all modules that depend on a module."""
        return self.reverse_dependency_graph.get(module_name, [])
    
    def find_circular_dependencies(self) -> List[List[str]]:
        """
        Find circular dependencies in the codebase.
        
        Returns:
            List of circular dependency chains
        """
        cycles = []
        visited = set()
        rec_stack = set()
        
        def dfs(module: str, path: List[str]) -> None:
            if module in rec_stack:
                # Found a cycle
                cycle_start = path.index(module)
                cycle = path[cycle_start:] + [module]
                
                # Normalize cycle (start with smallest name)
                min_idx = cycle.index(min(cycle[:-1]))
                normalized = cycle[min_idx:-1] + cycle[:min_idx] + [cycle[min_idx]]
                
                # Check if we've seen this cycle
                if normalized not in cycles:
                    cycles.append(normalized)
                return
            
            if module in visited:
                return
            
            visited.add(module)
            rec_stack.add(module)
            
            for dependency in self.dependency_graph.get(module, []):
                dfs(dependency, path + [dependency])
            
            rec_stack.remove(module)
        
        for module in self.dependency_graph.keys():
            if module not in visited:
                dfs(module, [module])
        
        return cycles
    
    def calculate_coupling_metrics(self) -> Dict[str, Dict[str, any]]:
        """
        Calculate coupling metrics for each module.
        
        Returns:
            Dictionary mapping module names to their coupling metrics
        """
        metrics = {}
        
        for module in set(self.dependency_graph.keys()) | set(self.reverse_dependency_graph.keys()):
            efferent = len(self.dependency_graph.get(module, []))  # outgoing
            afferent = len(self.reverse_dependency_graph.get(module, []))  # incoming
            
            # Calculate instability (I = efferent / (efferent + afferent))
            total = efferent + afferent
            instability = efferent / total if total > 0 else 0
            
            metrics[module] = {
                'efferent_coupling': efferent,  # Ce
                'afferent_coupling': afferent,   # Ca
                'instability': round(instability, 3),
                'total_coupling': total
            }
        
        return metrics
    
    def identify_highly_coupled_modules(self, threshold: int = 5) -> List[Tuple[str, int]]:
        """
        Identify modules with high coupling.
        
        Args:
            threshold: Coupling threshold
            
        Returns:
            List of (module_name, coupling_count) tuples
        """
        metrics = self.calculate_coupling_metrics()
        highly_coupled = [
            (module, m['total_coupling']) 
            for module, m in metrics.items() 
            if m['total_coupling'] >= threshold
        ]
        
        highly_coupled.sort(key=lambda x: x[1], reverse=True)
        return highly_coupled
    
    def get_dependency_layers(self) -> Dict[int, List[str]]:
        """
        Organize modules into dependency layers (0 = no dependencies).
        
        Returns:
            Dictionary mapping layer number to list of modules
        """
        layers = defaultdict(list)
        layer_map = {}
        
        def get_layer(module: str, visited: Set[str]) -> int:
            if module in layer_map:
                return layer_map[module]
            
            if module in visited:
                return 0  # Circular dependency, assign to layer 0
            
            visited.add(module)
            
            dependencies = self.dependency_graph.get(module, [])
            if not dependencies:
                layer_map[module] = 0
                return 0
            
            max_dep_layer = max(
                get_layer(dep, visited.copy()) 
                for dep in dependencies
            )
            
            layer = max_dep_layer + 1
            layer_map[module] = layer
            return layer
        
        for module in self.dependency_graph.keys():
            layer = get_layer(module, set())
            layers[layer].append(module)
        
        return dict(layers)
    
    def find_god_modules(self, threshold: int = 10) -> List[str]:
        """
        Find "God" modules that are depended on by many others.
        
        Args:
            threshold: Minimum number of dependents
            
        Returns:
            List of module names
        """
        god_modules = []
        
        for module, dependents in self.reverse_dependency_graph.items():
            if len(dependents) >= threshold:
                god_modules.append(module)
        
        return god_modules
    
    def find_leaf_modules(self) -> List[str]:
        """
        Find leaf modules (no other modules depend on them).
        
        Returns:
            List of module names
        """
        return [
            module for module in self.dependency_graph.keys()
            if module not in self.reverse_dependency_graph or not self.reverse_dependency_graph[module]
        ]
    
    def find_root_modules(self) -> List[str]:
        """
        Find root modules (depend on no other modules).
        
        Returns:
            List of module names
        """
        return [
            module for module in self.reverse_dependency_graph.keys()
            if module not in self.dependency_graph or not self.dependency_graph[module]
        ]
    
    def calculate_module_stability(self) -> Dict[str, float]:
        """
        Calculate stability metric for each module.
        Stability = Ca / (Ca + Ce)
        Higher stability = more depended upon, harder to change
        
        Returns:
            Dictionary mapping module names to stability scores
        """
        metrics = self.calculate_coupling_metrics()
        stability = {}
        
        for module, m in metrics.items():
            total = m['total_coupling']
            if total > 0:
                stability[module] = round(m['afferent_coupling'] / total, 3)
            else:
                stability[module] = 0.0
        
        return stability
    
    def get_dependency_tree(self, module_name: str, max_depth: int = 3) -> Dict:
        """
        Get a tree of dependencies for a module.
        
        Args:
            module_name: Name of the module
            max_depth: Maximum depth to traverse
            
        Returns:
            Nested dictionary representing dependency tree
        """
        def build_tree(module: str, depth: int, visited: Set[str]) -> Dict:
            if depth >= max_depth or module in visited:
                return {}
            
            visited.add(module)
            tree = {}
            
            for dep in self.dependency_graph.get(module, []):
                tree[dep] = build_tree(dep, depth + 1, visited.copy())
            
            return tree
        
        return {module_name: build_tree(module_name, 0, set())}
    
    def analyze_external_dependencies(self, analysis_result: AnalysisResult) -> Dict[str, int]:
        """
        Analyze external (third-party) dependencies.
        
        Args:
            analysis_result: The analysis result
            
        Returns:
            Dictionary mapping external package names to usage count
        """
        external_deps = defaultdict(int)
        module_names = {Path(path).stem for path in analysis_result.modules.keys()}
        
        for module_info in analysis_result.modules.values():
            for import_info in module_info.imports:
                base_module = self._extract_base_module(import_info.module)
                
                # If it's not an internal module, it's external
                if base_module not in module_names:
                    external_deps[base_module] += 1
        
        return dict(external_deps)
    
    def get_most_used_external_packages(self, analysis_result: AnalysisResult, 
                                       top_n: int = 10) -> List[Tuple[str, int]]:
        """
        Get the most frequently used external packages.
        
        Args:
            analysis_result: The analysis result
            top_n: Number of top packages to return
            
        Returns:
            List of (package_name, usage_count) tuples
        """
        external = self.analyze_external_dependencies(analysis_result)
        sorted_deps = sorted(external.items(), key=lambda x: x[1], reverse=True)
        return sorted_deps[:top_n]
    
    def detect_dependency_violations(self, 
                                    allowed_deps: Dict[str, List[str]]) -> List[str]:
        """
        Detect violations of defined dependency rules.
        
        Args:
            allowed_deps: Dictionary mapping modules to lists of allowed dependencies
            
        Returns:
            List of violation descriptions
        """
        violations = []
        
        for module, deps in self.dependency_graph.items():
            if module in allowed_deps:
                allowed = set(allowed_deps[module])
                actual = set(deps)
                
                forbidden = actual - allowed
                if forbidden:
                    violations.append(
                        f"{module} has forbidden dependencies: {', '.join(forbidden)}"
                    )
        
        return violations
    
    def _extract_base_module(self, module_path: str) -> str:
        """Extract the base module name from a module path."""
        if not module_path:
            return ""
        
        # Handle relative imports
        module_path = module_path.lstrip('.')
        
        # Get the first part of the module path
        parts = module_path.split('.')
        return parts[0] if parts else module_path