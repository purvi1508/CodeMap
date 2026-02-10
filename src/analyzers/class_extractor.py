"""
Class extractor - extracts and analyzes class hierarchies.
"""
from typing import Dict, List, Set, Optional, Tuple
from pathlib import Path

from .models import ClassInfo, ModuleInfo, AnalysisResult
from .ast_analyzer import ASTAnalyzer


class ClassExtractor:
    """Extracts and analyzes class structures and relationships."""
    
    def __init__(self):
        """Initialize the class extractor."""
        self.ast_analyzer = ASTAnalyzer()
        self.class_hierarchy = {}  # class_name -> parent classes
        self.inheritance_tree = {}  # class_name -> child classes
    
    def extract_from_modules(self, analysis_result: AnalysisResult) -> List[ClassInfo]:
        """
        Extract all classes from analysis result.
        
        Args:
            analysis_result: The analysis result containing modules
            
        Returns:
            List of all ClassInfo objects
        """
        all_classes = []
        
        for module_info in analysis_result.modules.values():
            all_classes.extend(module_info.classes)
        
        # Build hierarchy
        self._build_hierarchy(all_classes)
        
        return all_classes
    
    def get_class_hierarchy(self, class_name: str) -> Dict[str, List[str]]:
        """
        Get the complete hierarchy for a class (ancestors and descendants).
        
        Args:
            class_name: Name of the class
            
        Returns:
            Dictionary with 'ancestors' and 'descendants' lists
        """
        return {
            'ancestors': self._get_ancestors(class_name),
            'descendants': self._get_descendants(class_name)
        }
    
    def find_class_by_name(self, classes: List[ClassInfo], name: str) -> Optional[ClassInfo]:
        """Find a class by name."""
        return next((cls for cls in classes if cls.name == name), None)
    
    def get_classes_by_base(self, classes: List[ClassInfo], base_name: str) -> List[ClassInfo]:
        """Get all classes that inherit from a specific base class."""
        return [cls for cls in classes if base_name in cls.base_classes]
    
    def get_abstract_classes(self, classes: List[ClassInfo]) -> List[ClassInfo]:
        """Get all abstract classes."""
        return [cls for cls in classes if cls.is_abstract]
    
    def get_dataclasses(self, classes: List[ClassInfo]) -> List[ClassInfo]:
        """Get all dataclasses."""
        return [cls for cls in classes if cls.is_dataclass]
    
    def analyze_class_complexity(self, class_info: ClassInfo) -> Dict[str, any]:
        """
        Analyze the complexity of a class.
        
        Args:
            class_info: The class to analyze
            
        Returns:
            Dictionary with complexity metrics
        """
        total_methods = len(class_info.methods)
        public_methods = len(class_info.get_public_methods())
        
        # Calculate average method complexity
        if class_info.methods:
            avg_complexity = sum(m.complexity for m in class_info.methods) / len(class_info.methods)
        else:
            avg_complexity = 0
        
        # Calculate lines of code
        loc = class_info.end_line_number - class_info.line_number + 1
        
        return {
            'name': class_info.name,
            'total_methods': total_methods,
            'public_methods': public_methods,
            'private_methods': total_methods - public_methods,
            'attributes': len(class_info.attributes),
            'base_classes': len(class_info.base_classes),
            'inner_classes': len(class_info.inner_classes),
            'lines_of_code': loc,
            'average_method_complexity': round(avg_complexity, 2),
            'has_constructor': class_info.get_constructor() is not None,
            'is_abstract': class_info.is_abstract,
            'is_dataclass': class_info.is_dataclass
        }
    
    def detect_design_patterns(self, classes: List[ClassInfo]) -> Dict[str, List[str]]:
        """
        Detect common design patterns in classes.
        
        Args:
            classes: List of classes to analyze
            
        Returns:
            Dictionary mapping pattern names to class names
        """
        patterns = {
            'Singleton': [],
            'Factory': [],
            'Builder': [],
            'Adapter': [],
            'Decorator': [],
            'Observer': [],
        }
        
        for cls in classes:
            class_name_lower = cls.name.lower()
            
            # Singleton: has private constructor and getInstance method
            constructor = cls.get_constructor()
            has_get_instance = any(
                m.name in ['get_instance', 'getInstance'] 
                for m in cls.methods
            )
            if constructor and has_get_instance:
                patterns['Singleton'].append(cls.name)
            
            # Factory: name contains 'factory' or has 'create' methods
            if 'factory' in class_name_lower:
                patterns['Factory'].append(cls.name)
            elif any(m.name.startswith('create') for m in cls.methods):
                patterns['Factory'].append(cls.name)
            
            # Builder: name contains 'builder' or has 'build' method
            if 'builder' in class_name_lower:
                patterns['Builder'].append(cls.name)
            elif any(m.name == 'build' for m in cls.methods):
                patterns['Builder'].append(cls.name)
            
            # Adapter: name contains 'adapter'
            if 'adapter' in class_name_lower:
                patterns['Adapter'].append(cls.name)
            
            # Decorator: name contains 'decorator'
            if 'decorator' in class_name_lower:
                patterns['Decorator'].append(cls.name)
            
            # Observer: has subscribe/notify pattern
            has_subscribe = any('subscribe' in m.name.lower() for m in cls.methods)
            has_notify = any('notify' in m.name.lower() for m in cls.methods)
            if has_subscribe or has_notify:
                patterns['Observer'].append(cls.name)
        
        # Remove empty patterns
        return {k: v for k, v in patterns.items() if v}
    
    def get_method_override_analysis(self, classes: List[ClassInfo]) -> Dict[str, List[str]]:
        """
        Analyze method overrides across class hierarchy.
        
        Args:
            classes: List of classes to analyze
            
        Returns:
            Dictionary mapping class names to list of overridden methods
        """
        overrides = {}
        
        for cls in classes:
            if not cls.base_classes:
                continue
            
            overridden = []
            method_names = {m.name for m in cls.methods}
            
            # Find parent classes
            for parent_name in cls.base_classes:
                parent = self.find_class_by_name(classes, parent_name)
                if parent:
                    parent_methods = {m.name for m in parent.methods}
                    overridden.extend(method_names & parent_methods)
            
            if overridden:
                overrides[cls.name] = list(set(overridden))
        
        return overrides
    
    def _build_hierarchy(self, classes: List[ClassInfo]):
        """Build class hierarchy maps."""
        self.class_hierarchy.clear()
        self.inheritance_tree.clear()
        
        # Build class hierarchy (class -> parents)
        for cls in classes:
            self.class_hierarchy[cls.name] = cls.base_classes
        
        # Build inheritance tree (parent -> children)
        for cls in classes:
            for base in cls.base_classes:
                if base not in self.inheritance_tree:
                    self.inheritance_tree[base] = []
                self.inheritance_tree[base].append(cls.name)
    
    def _get_ancestors(self, class_name: str) -> List[str]:
        """Get all ancestor classes (recursive)."""
        ancestors = []
        
        if class_name not in self.class_hierarchy:
            return ancestors
        
        for parent in self.class_hierarchy[class_name]:
            ancestors.append(parent)
            ancestors.extend(self._get_ancestors(parent))
        
        return list(set(ancestors))  # Remove duplicates
    
    def _get_descendants(self, class_name: str) -> List[str]:
        """Get all descendant classes (recursive)."""
        descendants = []
        
        if class_name not in self.inheritance_tree:
            return descendants
        
        for child in self.inheritance_tree[class_name]:
            descendants.append(child)
            descendants.extend(self._get_descendants(child))
        
        return list(set(descendants))  # Remove duplicates
    
    def get_class_relationships(self, classes: List[ClassInfo]) -> List[Tuple[str, str, str]]:
        """
        Get all class relationships.
        
        Returns:
            List of tuples (source_class, relationship_type, target_class)
            Relationship types: 'inherits', 'contains', 'uses'
        """
        relationships = []
        
        for cls in classes:
            # Inheritance relationships
            for base in cls.base_classes:
                relationships.append((cls.name, 'inherits', base))
            
            # Composition (class attributes that are other classes)
            for attr in cls.attributes:
                # Check if attribute type matches another class
                for other_cls in classes:
                    if other_cls.name.lower() in attr.lower():
                        relationships.append((cls.name, 'contains', other_cls.name))
            
            # Usage (method parameters or return types)
            for method in cls.methods:
                # Check parameters
                for param in method.parameters:
                    if param.type_annotation:
                        for other_cls in classes:
                            if other_cls.name == param.type_annotation:
                                relationships.append((cls.name, 'uses', other_cls.name))
                
                # Check return type
                if method.return_type:
                    for other_cls in classes:
                        if other_cls.name == method.return_type:
                            relationships.append((cls.name, 'uses', other_cls.name))
        
        return list(set(relationships))  # Remove duplicates