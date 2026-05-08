from __future__ import annotations

import ast
import datetime
import json
from dataclasses import dataclass
from pathlib import Path


# ── constants ──────────────────────────────────────────────────────────────────

SKIP_DIRS: frozenset[str] = frozenset({
    '.git', '__pycache__', 'node_modules',
    '.tox', '.venv', 'venv', 'env',
    'dist', 'build',
    '.mypy_cache', '.pytest_cache', '.ruff_cache',
    '.idea', '.vscode',
})

SOURCE_EXTENSIONS: frozenset[str] = frozenset({
    '.py', '.js', '.ts', '.jsx', '.tsx', '.mjs',
    '.go', '.rb', '.java', '.rs',
    '.c', '.cpp', '.cc', '.h', '.hpp',
    '.sh', '.bash',
    '.swift', '.kt',
    '.php', '.cs', '.lua',
})

_CONFIG_NAMES: frozenset[str] = frozenset({
    'pyproject.toml', 'setup.py', 'setup.cfg',
    'package.json', 'Cargo.toml', 'go.mod',
    'Makefile', 'makefile', 'Dockerfile',
    'requirements.txt', 'tox.ini',
    'tsconfig.json',
})

_LANGUAGE_MAP: dict[str, str] = {
    '.py': 'python',
    '.js': 'javascript', '.jsx': 'javascript', '.mjs': 'javascript',
    '.ts': 'typescript', '.tsx': 'typescript',
    '.go': 'go',
    '.rb': 'ruby',
    '.java': 'java',
    '.rs': 'rust',
    '.c': 'c', '.h': 'c',
    '.cpp': 'cpp', '.cc': 'cpp', '.hpp': 'cpp',
    '.sh': 'shell', '.bash': 'shell',
    '.swift': 'swift',
    '.kt': 'kotlin', '.kts': 'kotlin',
    '.php': 'php',
    '.cs': 'csharp',
    '.lua': 'lua',
}


# ── data model ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SymbolInfo:
    """Extracted symbol (class, function, or method) from a source file."""

    name: str
    kind: str       # 'class', 'function', 'async function', 'method', 'async method', 'property'
    signature: str  # positional arg names joined by ', '
    summary: str    # first docstring line, or empty string
    is_private: bool
    children: tuple[SymbolInfo, ...] = ()


@dataclass(frozen=True)
class FileEntry:
    """Single source file with extracted metadata."""

    path: Path      # relative to project root
    language: str
    summary: str    # module-level first docstring line
    symbols: tuple[SymbolInfo, ...]


@dataclass(frozen=True)
class EntryPoint:
    """Detected project entry point."""

    description: str


@dataclass(frozen=True)
class MapResult:
    """Result of a map run."""

    root: Path
    project_name: str
    generated_at: str
    output_path: Path
    files: tuple[FileEntry, ...]
    entry_points: tuple[EntryPoint, ...]

    @property
    def file_count(self) -> int:
        return len(self.files)

    @property
    def symbol_count(self) -> int:
        total = 0
        for f in self.files:
            total += len(f.symbols)
            for s in f.symbols:
                total += len(s.children)
        return total


# ── public API ─────────────────────────────────────────────────────────────────

def run_map(
    root: Path,
    output: Path | None = None,
    include_private: bool = False,
) -> MapResult:
    """Generate a Markdown code map for the project at root and write it to output."""
    root = root.resolve()
    if output is None:
        output = root / 'docs' / 'codemap.md'
    output = output.resolve()

    gitignore_patterns = _load_gitignore(root)

    result = MapResult(
        root=root,
        project_name=_detect_project_name(root),
        generated_at=datetime.date.today().isoformat(),
        output_path=output,
        files=tuple(_collect_files(root, include_private, output, gitignore_patterns)),
        entry_points=tuple(_detect_entry_points(root)),
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(_render_markdown(result), encoding='utf-8')
    return result


# ── file traversal ─────────────────────────────────────────────────────────────

def _should_skip_dir(name: str) -> bool:
    return name in SKIP_DIRS or name.endswith(('.egg-info', '.dist-info'))


def _should_include(path: Path) -> bool:
    return path.suffix in SOURCE_EXTENSIONS or path.name in _CONFIG_NAMES


def _detect_language(path: Path) -> str:
    return _LANGUAGE_MAP.get(
        path.suffix,
        'config' if path.name in _CONFIG_NAMES else 'unknown',
    )


def _load_gitignore(root: Path) -> list[str]:
    """Return non-comment, non-empty patterns from root/.gitignore."""
    gitignore = root / '.gitignore'
    if not gitignore.is_file():
        return []
    patterns: list[str] = []
    try:
        for line in gitignore.read_text(encoding='utf-8', errors='replace').splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith('#'):
                patterns.append(stripped)
    except OSError:
        pass
    return patterns


def _is_gitignored(rel_path: Path, patterns: list[str]) -> bool:
    """Return True if rel_path matches any .gitignore pattern (simple glob, no negation)."""
    for pattern in patterns:
        if pattern.startswith('!'):
            continue
        # Match against filename alone or full relative path
        if rel_path.match(pattern) or rel_path.name == pattern.lstrip('/'):
            return True
        # Directory patterns (trailing slash) — match any part
        if pattern.endswith('/') and any(
            part == pattern.rstrip('/') for part in rel_path.parts
        ):
            return True
    return False


def _walk_source(directory: Path, root: Path, patterns: list[str]):
    """Yield all includable source files under directory, skipping irrelevant dirs."""
    try:
        items = sorted(directory.iterdir())
    except PermissionError:
        return
    for item in items:
        rel = item.relative_to(root)
        if _is_gitignored(rel, patterns):
            continue
        if item.is_dir():
            if not _should_skip_dir(item.name):
                yield from _walk_source(item, root, patterns)
        elif item.is_file() and _should_include(item):
            yield item


def _collect_files(
    root: Path,
    include_private: bool,
    output_path: Path,
    gitignore_patterns: list[str],
) -> list[FileEntry]:
    entries: list[FileEntry] = []
    for file_path in _walk_source(root, root, gitignore_patterns):
        if file_path.resolve() == output_path:
            continue
        language = _detect_language(file_path)
        summary = ''
        symbols: tuple[SymbolInfo, ...] = ()

        if language == 'python':
            summary, symbols = _parse_python(file_path, include_private)

        entries.append(FileEntry(
            path=file_path.relative_to(root),
            language=language,
            summary=summary,
            symbols=symbols,
        ))
    return entries


# ── Python AST extraction ──────────────────────────────────────────────────────

def _parse_python(path: Path, include_private: bool) -> tuple[str, tuple[SymbolInfo, ...]]:
    """Extract module docstring and top-level symbols from a Python source file."""
    try:
        source = path.read_text(encoding='utf-8', errors='replace')
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return '', ()

    symbols: list[SymbolInfo] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            if _is_private(node.name) and not include_private:
                continue
            symbols.append(SymbolInfo(
                name=node.name,
                kind='class',
                signature='',
                summary=_first_docstring_line(node),
                is_private=_is_private(node.name),
                children=tuple(_extract_methods(node, include_private)),
            ))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if _is_private(node.name) and not include_private:
                continue
            symbols.append(SymbolInfo(
                name=node.name,
                kind='async function' if isinstance(node, ast.AsyncFunctionDef) else 'function',
                signature=_format_args(node.args),
                summary=_first_docstring_line(node),
                is_private=_is_private(node.name),
            ))

    return _first_docstring_line(tree), tuple(symbols)


def _extract_methods(class_node: ast.ClassDef, include_private: bool) -> list[SymbolInfo]:
    methods: list[SymbolInfo] = []
    for node in ast.iter_child_nodes(class_node):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if _is_private(node.name) and not include_private:
            continue
        decorators = {
            getattr(d, 'id', None) or getattr(d, 'attr', None)
            for d in node.decorator_list
        }
        if decorators & {'property', 'setter', 'deleter'}:
            kind = 'property'
        elif isinstance(node, ast.AsyncFunctionDef):
            kind = 'async method'
        else:
            kind = 'method'
        methods.append(SymbolInfo(
            name=node.name,
            kind=kind,
            signature=_format_args(node.args),
            summary=_first_docstring_line(node),
            is_private=_is_private(node.name),
        ))
    return methods


def _is_private(name: str) -> bool:
    """Single-underscore names are private; dunder names (__x__) are not."""
    return name.startswith('_') and not name.startswith('__')


def _first_docstring_line(node: ast.AST) -> str:
    body = getattr(node, 'body', [])
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        return body[0].value.value.strip().splitlines()[0]
    return ''


def _format_args(args: ast.arguments) -> str:
    parts = [a.arg for a in args.args]
    if args.vararg:
        parts.append(f'*{args.vararg.arg}')
    if args.kwarg:
        parts.append(f'**{args.kwarg.arg}')
    return ', '.join(parts)


# ── entry point and project detection ─────────────────────────────────────────

def _detect_project_name(root: Path) -> str:
    pyproject = root / 'pyproject.toml'
    if pyproject.is_file():
        try:
            content = pyproject.read_text(encoding='utf-8')
            in_project = False
            for line in content.splitlines():
                stripped = line.strip()
                if stripped == '[project]':
                    in_project = True
                    continue
                if in_project:
                    if stripped.startswith('['):
                        break
                    if stripped.startswith('name') and '=' in stripped:
                        _, value = stripped.split('=', 1)
                        return value.strip().strip('"\'')
        except OSError:
            pass

    package_json = root / 'package.json'
    if package_json.is_file():
        try:
            data = json.loads(package_json.read_text(encoding='utf-8'))
            if isinstance(data.get('name'), str):
                return data['name']
        except (OSError, json.JSONDecodeError):
            pass

    return root.name


def _detect_entry_points(root: Path) -> list[EntryPoint]:
    entry_points: list[EntryPoint] = []

    pyproject = root / 'pyproject.toml'
    if pyproject.is_file():
        try:
            content = pyproject.read_text(encoding='utf-8')
            in_scripts = False
            for line in content.splitlines():
                stripped = line.strip()
                if stripped == '[project.scripts]':
                    in_scripts = True
                    continue
                if in_scripts:
                    if stripped.startswith('['):
                        break
                    if '=' in stripped and not stripped.startswith('#'):
                        cmd, target = stripped.split('=', 1)
                        cmd = cmd.strip().strip('"\'')
                        target = target.strip().strip('"\'')
                        entry_points.append(EntryPoint(f'`{cmd}` command → `{target}`'))
        except OSError:
            pass

    for file_path in _walk_source(root, root, []):
        if file_path.name == '__main__.py':
            rel = file_path.relative_to(root)
            pkg = '.'.join(rel.parts[:-1])
            if pkg:
                entry_points.append(EntryPoint(f'`{rel}` — `python -m {pkg}`'))

    return entry_points


# ── Markdown rendering ─────────────────────────────────────────────────────────

def _render_markdown(result: MapResult) -> str:
    lines: list[str] = []

    lines += [
        f'# Code Map · {result.project_name}',
        '',
        f'> Generated: {result.generated_at} · Root: `{result.root}`  ',
        f'> Refresh: `governancekit map`',
        '',
        f'{result.file_count} file(s) · {result.symbol_count} symbol(s) indexed',
        '',
    ]

    if result.entry_points:
        lines += ['## Entry Points', '']
        for ep in result.entry_points:
            lines.append(f'- {ep.description}')
        lines.append('')

    lines += ['## File Tree', '', '```']
    lines += _render_tree(result.files)
    lines += ['```', '']

    python_with_symbols = [f for f in result.files if f.language == 'python' and f.symbols]
    if python_with_symbols:
        lines += ['## Symbol Index', '']
        for entry in python_with_symbols:
            lines += _render_file_symbols(entry)

    return '\n'.join(lines) + '\n'


def _render_tree(files: tuple[FileEntry, ...]) -> list[str]:
    """Render a compact indented file tree."""
    lines: list[str] = []
    prev_dirs: tuple[str, ...] = ()

    for entry in files:
        parts = entry.path.parts
        dir_parts = parts[:-1]
        filename = parts[-1]

        for i, part in enumerate(dir_parts):
            if i >= len(prev_dirs) or prev_dirs[i] != part:
                lines.append('  ' * i + part + '/')

        indent = '  ' * len(dir_parts)
        if entry.summary:
            lines.append(f'{indent}{filename}  — "{entry.summary}"')
        else:
            lines.append(f'{indent}{filename}')

        prev_dirs = dir_parts

    return lines


def _render_file_symbols(entry: FileEntry) -> list[str]:
    lines: list[str] = [f'### `{entry.path}`', '']
    if entry.summary:
        lines += [f'> {entry.summary}', '']
    for symbol in entry.symbols:
        lines += _render_symbol(symbol, depth=0)
    lines.append('')
    return lines


def _render_symbol(symbol: SymbolInfo, depth: int) -> list[str]:
    indent = '  ' * depth
    summary_part = f' — "{symbol.summary}"' if symbol.summary else ''
    private_part = ' *(internal)*' if symbol.is_private else ''

    if symbol.kind == 'class':
        lines = [f'{indent}- **`{symbol.name}`** *(class)*{private_part}{summary_part}']
        for child in symbol.children:
            lines += _render_symbol(child, depth + 1)
        return lines

    sig = f'({symbol.signature})' if symbol.kind != 'property' else ''
    kind_label = '' if symbol.kind == 'function' else f' *({symbol.kind})*'
    return [f'{indent}- `{symbol.name}{sig}`{kind_label}{private_part}{summary_part}']
