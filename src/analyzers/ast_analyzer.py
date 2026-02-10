"""
AST (Abstract Syntax Tree) analyzer for Python code.
"""
import ast
from pathlib import Path
from typing import Optional, List, Set

from .models import (
    ModuleInfo, ClassInfo, FunctionInfo, ImportInfo,
    Parameter, NodeType, CallGraphEdge, Visibility
)


class ASTAnalyzer:
    """Analyzes Python code using AST parsing."""
    
    def __init__(self):
        """Initialize the AST analyzer."""
        self.current_class = None
        self.current_function = None
        self.call_graph_edges = []
    
    def analyze_file(self, file_path: Path, content: str) -> Optional[ModuleInfo]:
        """
        Analyze a Python file and extract structural information.
        
        Args:
            file_path: Path to the file
            content: File content as string
            
        Returns:
            ModuleInfo object or None if parsing fails
        """
        try:
            tree = ast.parse(content, filename=str(file_path))
            
            module_info = ModuleInfo(
                name=file_path.stem,
                file_path=file_path,
                total_lines=len(content.split('\n'))
            )
            
            # Extract module docstring
            module_info.docstring = ast.get_docstring(tree)
            
            # Visit all nodes in the tree
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    module_info.imports.append(self._extract_import(node))
                elif isinstance(node, ast.ImportFrom):
                    module_info.imports.append(self._extract_from_import(node))
            
            # Process top-level nodes
            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    class_info = self._extract_class(node)
                    module_info.classes.append(class_info)
                elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                    func_info = self._extract_function(node, NodeType.FUNCTION)
                    module_info.functions.append(func_info)
                elif isinstance(node, ast.Assign):
                    # Extract global variables and constants
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            name = target.id
                            if name.isupper():
                                module_info.constants.append(name)
                            else:
                                module_info.global_variables.append(name)
            
            return module_info
            
        except SyntaxError as e:
            return None
        except Exception as e:
            return None
    
    def _extract_import(self, node: ast.Import) -> ImportInfo:
        """Extract information from an import statement."""
        # Handle: import module [as alias]
        names = [alias.name for alias in node.names]
        alias = node.names[0].asname if len(node.names) == 1 else None
        
        return ImportInfo(
            module=names[0] if names else "",
            names=names,
            alias=alias,
            is_from_import=False,
            line_number=node.lineno
        )
    
    def _extract_from_import(self, node: ast.ImportFrom) -> ImportInfo:
        """Extract information from a from...import statement."""
        # Handle: from module import name [as alias]
        names = [alias.name for alias in node.names]
        
        return ImportInfo(
            module=node.module or "",
            names=names,
            alias=None,
            is_from_import=True,
            line_number=node.lineno
        )
    
    def _extract_class(self, node: ast.ClassDef) -> ClassInfo:
        """Extract information from a class definition."""
        class_info = ClassInfo(
            name=node.name,
            line_number=node.lineno,
            end_line_number=node.end_lineno or node.lineno,
            docstring=ast.get_docstring(node)
        )
        
        # Extract base classes
        for base in node.bases:
            if isinstance(base, ast.Name):
                class_info.base_classes.append(base.id)
            elif isinstance(base, ast.Attribute):
                class_info.base_classes.append(self._get_attribute_name(base))
        
        # Extract decorators
        class_info.decorators = [self._get_decorator_name(dec) for dec in node.decorator_list]
        
        # Check if it's a dataclass
        class_info.is_dataclass = 'dataclass' in class_info.decorators
        
        # Check if it's abstract
        class_info.is_abstract = any(
            base in ['ABC', 'ABCMeta'] for base in class_info.base_classes
        )
        
        # Extract methods and attributes
        self.current_class = class_info
        
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                method_info = self._extract_function(item, NodeType.METHOD)
                class_info.methods.append(method_info)
            elif isinstance(item, ast.Assign):
                # Class-level attributes
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        class_info.attributes.append(target.id)
            elif isinstance(item, ast.AnnAssign):
                # Type-annotated attributes
                if isinstance(item.target, ast.Name):
                    class_info.attributes.append(item.target.id)
            elif isinstance(item, ast.ClassDef):
                # Inner classes
                inner_class = self._extract_class(item)
                class_info.inner_classes.append(inner_class)
        
        self.current_class = None
        
        return class_info
    
    def _extract_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef, 
                         node_type: NodeType) -> FunctionInfo:
        """Extract information from a function or method definition."""
        func_info = FunctionInfo(
            name=node.name,
            node_type=node_type,
            line_number=node.lineno,
            end_line_number=node.end_lineno or node.lineno,
            docstring=ast.get_docstring(node),
            is_async=isinstance(node, ast.AsyncFunctionDef)
        )
        
        # Extract decorators
        func_info.decorators = [self._get_decorator_name(dec) for dec in node.decorator_list]
        func_info.is_property = 'property' in func_info.decorators
        
        # Extract parameters
        func_info.parameters = self._extract_parameters(node.args)
        
        # Extract return type
        if node.returns:
            func_info.return_type = self._get_type_annotation(node.returns)
        
        # Extract function calls (for call graph)
        self.current_function = func_info.name
        func_info.calls = self._extract_function_calls(node)
        self.current_function = None
        
        # Calculate cyclomatic complexity (basic)
        func_info.complexity = self._calculate_complexity(node)
        
        return func_info
    
    def _extract_parameters(self, args: ast.arguments) -> List[Parameter]:
        """Extract function parameters."""
        parameters = []
        
        # Regular positional arguments
        for i, arg in enumerate(args.args):
            # Skip 'self' and 'cls' for methods
            if self.current_class and i == 0 and arg.arg in ['self', 'cls']:
                continue
            
            param = Parameter(
                name=arg.arg,
                type_annotation=self._get_type_annotation(arg.annotation) if arg.annotation else None
            )
            
            # Check for default values
            defaults_offset = len(args.args) - len(args.defaults)
            if i >= defaults_offset:
                default_idx = i - defaults_offset
                param.default_value = self._get_default_value(args.defaults[default_idx])
            
            parameters.append(param)
        
        # Keyword-only arguments
        for i, arg in enumerate(args.kwonlyargs):
            param = Parameter(
                name=arg.arg,
                type_annotation=self._get_type_annotation(arg.annotation) if arg.annotation else None,
                is_keyword_only=True
            )
            
            if i < len(args.kw_defaults) and args.kw_defaults[i]:
                param.default_value = self._get_default_value(args.kw_defaults[i])
            
            parameters.append(param)
        
        # *args
        if args.vararg:
            parameters.append(Parameter(
                name=f"*{args.vararg.arg}",
                type_annotation=self._get_type_annotation(args.vararg.annotation) if args.vararg.annotation else None
            ))
        
        # **kwargs
        if args.kwarg:
            parameters.append(Parameter(
                name=f"**{args.kwarg.arg}",
                type_annotation=self._get_type_annotation(args.kwarg.annotation) if args.kwarg.annotation else None
            ))
        
        return parameters
    
    def _extract_function_calls(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> List[str]:
        """Extract all function calls within a function."""
        calls = []
        
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                call_name = self._get_call_name(child.func)
                if call_name:
                    calls.append(call_name)
        
        return list(set(calls))  # Remove duplicates
    
    def _get_call_name(self, node: ast.expr) -> Optional[str]:
        """Get the name of a function being called."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return self._get_attribute_name(node)
        return None
    
    def _get_attribute_name(self, node: ast.Attribute) -> str:
        """Get the full name of an attribute access."""
        parts = []
        current = node
        
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        
        if isinstance(current, ast.Name):
            parts.append(current.id)
        
        return '.'.join(reversed(parts))
    
    def _get_decorator_name(self, node: ast.expr) -> str:
        """Get the name of a decorator."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return self._get_attribute_name(node)
        elif isinstance(node, ast.Call):
            return self._get_decorator_name(node.func)
        return "unknown"
    
    def _get_type_annotation(self, node: ast.expr) -> str:
        """Get string representation of a type annotation."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Constant):
            return str(node.value)
        elif isinstance(node, ast.Attribute):
            return self._get_attribute_name(node)
        elif isinstance(node, ast.Subscript):
            # Handle List[int], Dict[str, int], etc.
            base = self._get_type_annotation(node.value)
            if isinstance(node.slice, ast.Tuple):
                args = ', '.join(self._get_type_annotation(elt) for elt in node.slice.elts)
            else:
                args = self._get_type_annotation(node.slice)
            return f"{base}[{args}]"
        return "Any"
    
    def _get_default_value(self, node: ast.expr) -> str:
        """Get string representation of a default value."""
        if isinstance(node, ast.Constant):
            if isinstance(node.value, str):
                return f"'{node.value}'"
            return str(node.value)
        elif isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.List):
            return "[]"
        elif isinstance(node, ast.Dict):
            return "{}"
        elif isinstance(node, ast.Set):
            return "set()"
        return "..."
    
    def _calculate_complexity(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
        """Calculate cyclomatic complexity (basic version)."""
        complexity = 1
        
        for child in ast.walk(node):
            # Decision points add to complexity
            if isinstance(child, (ast.If, ast.While, ast.For, ast.AsyncFor)):
                complexity += 1
            elif isinstance(child, ast.ExceptHandler):
                complexity += 1
            elif isinstance(child, (ast.And, ast.Or)):
                complexity += 1
            elif isinstance(child, ast.comprehension):
                complexity += 1
        
        return complexity