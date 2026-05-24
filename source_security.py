from __future__ import annotations

import ast
from dataclasses import dataclass, field


ALLOWED_IMPORT_ROOTS = {
    "__future__",
    "argparse",
    "cadquery",
    "dataclasses",
    "json",
    "math",
    "re",
    "pathlib",
    "typing",
}

BANNED_IMPORT_ROOTS = {
    "builtins",
    "ctypes",
    "glob",
    "httpx",
    "importlib",
    "inspect",
    "multiprocessing",
    "os",
    "pickle",
    "requests",
    "shutil",
    "socket",
    "subprocess",
    "sys",
    "threading",
    "urllib",
}

BANNED_CALLS = {
    "__import__",
    "breakpoint",
    "compile",
    "eval",
    "exec",
    "globals",
    "input",
    "locals",
    "open",
}


@dataclass
class SourceSecurityResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def model_dump(self) -> dict:
        return {"ok": self.ok, "errors": self.errors, "warnings": self.warnings}


def _root_name(module: str | None) -> str:
    return (module or "").split(".", 1)[0]


def validate_cad_source(source: str) -> SourceSecurityResult:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return SourceSecurityResult(False, [f"syntax_error:{exc.msg}:{exc.lineno}:{exc.offset}"], warnings)

    has_build_model = False
    has_export_outputs = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = _root_name(alias.name)
                if root in BANNED_IMPORT_ROOTS:
                    errors.append(f"banned_import:{alias.name}")
                elif root not in ALLOWED_IMPORT_ROOTS:
                    errors.append(f"unknown_import:{alias.name}")
        elif isinstance(node, ast.ImportFrom):
            root = _root_name(node.module)
            if root in BANNED_IMPORT_ROOTS:
                errors.append(f"banned_import:{node.module}")
            elif root not in ALLOWED_IMPORT_ROOTS:
                errors.append(f"unknown_import:{node.module}")
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in BANNED_CALLS:
                errors.append(f"banned_call:{func.id}")
            if isinstance(func, ast.Attribute) and func.attr in {"system", "popen", "spawn", "fork", "connect", "request", "urlopen"}:
                errors.append(f"banned_attribute_call:{func.attr}")
        elif isinstance(node, ast.FunctionDef):
            has_build_model = has_build_model or node.name == "build_model"
            has_export_outputs = has_export_outputs or node.name == "export_outputs"

    if not has_build_model:
        errors.append("missing_function:build_model")
    if not has_export_outputs:
        warnings.append("missing_function:export_outputs")

    return SourceSecurityResult(not errors, sorted(set(errors)), sorted(set(warnings)))
