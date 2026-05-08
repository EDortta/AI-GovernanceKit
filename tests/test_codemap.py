from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from governancekit.codemap import (
    _detect_project_name,
    _detect_entry_points,
    _is_private,
    _parse_python,
    run_map,
)


class IsPrivateTests(unittest.TestCase):
    def test_single_underscore_is_private(self) -> None:
        self.assertTrue(_is_private("_helper"))

    def test_dunder_is_not_private(self) -> None:
        self.assertFalse(_is_private("__init__"))
        self.assertFalse(_is_private("__repr__"))

    def test_plain_name_is_not_private(self) -> None:
        self.assertFalse(_is_private("run_map"))


class ParsePythonTests(unittest.TestCase):
    def _write(self, root: Path, src: str) -> Path:
        p = root / "module.py"
        p.write_text(src, encoding="utf-8")
        return p

    def test_extracts_module_docstring(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = self._write(Path(tmp), '"""Module summary."""\n\ndef foo(): pass\n')
            summary, _ = _parse_python(p, include_private=False)
            self.assertEqual(summary, "Module summary.")

    def test_extracts_function(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = self._write(Path(tmp), 'def add(a, b):\n    """Add two numbers."""\n    return a + b\n')
            _, symbols = _parse_python(p, include_private=False)
            self.assertEqual(len(symbols), 1)
            self.assertEqual(symbols[0].name, "add")
            self.assertEqual(symbols[0].kind, "function")
            self.assertEqual(symbols[0].signature, "a, b")
            self.assertEqual(symbols[0].summary, "Add two numbers.")

    def test_extracts_async_function(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = self._write(Path(tmp), "async def fetch(url):\n    pass\n")
            _, symbols = _parse_python(p, include_private=False)
            self.assertEqual(symbols[0].kind, "async function")

    def test_extracts_class_with_methods(self) -> None:
        src = (
            'class Dog:\n'
            '    """A dog."""\n'
            '    def bark(self):\n'
            '        """Make noise."""\n'
            '        pass\n'
        )
        with tempfile.TemporaryDirectory() as tmp:
            p = self._write(Path(tmp), src)
            _, symbols = _parse_python(p, include_private=False)
            self.assertEqual(len(symbols), 1)
            cls = symbols[0]
            self.assertEqual(cls.name, "Dog")
            self.assertEqual(cls.kind, "class")
            self.assertEqual(cls.summary, "A dog.")
            self.assertEqual(len(cls.children), 1)
            self.assertEqual(cls.children[0].name, "bark")
            self.assertEqual(cls.children[0].kind, "method")

    def test_skips_private_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = self._write(Path(tmp), "def _helper(): pass\ndef public(): pass\n")
            _, symbols = _parse_python(p, include_private=False)
            names = [s.name for s in symbols]
            self.assertNotIn("_helper", names)
            self.assertIn("public", names)

    def test_includes_private_when_flag_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = self._write(Path(tmp), "def _helper(): pass\n")
            _, symbols = _parse_python(p, include_private=True)
            self.assertEqual(symbols[0].name, "_helper")

    def test_property_kind(self) -> None:
        src = (
            "class C:\n"
            "    @property\n"
            "    def value(self): return 1\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            p = self._write(Path(tmp), src)
            _, symbols = _parse_python(p, include_private=False)
            self.assertEqual(symbols[0].children[0].kind, "property")

    def test_syntax_error_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = self._write(Path(tmp), "def (\n")
            summary, symbols = _parse_python(p, include_private=False)
            self.assertEqual(summary, "")
            self.assertEqual(symbols, ())

    def test_vararg_and_kwarg(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = self._write(Path(tmp), "def f(*args, **kwargs): pass\n")
            _, symbols = _parse_python(p, include_private=False)
            self.assertEqual(symbols[0].signature, "*args, **kwargs")


class DetectProjectNameTests(unittest.TestCase):
    def test_reads_pyproject_toml(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pyproject.toml").write_text(
                "[project]\nname = \"my-lib\"\n", encoding="utf-8"
            )
            self.assertEqual(_detect_project_name(root), "my-lib")

    def test_reads_package_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text('{"name": "my-pkg"}', encoding="utf-8")
            self.assertEqual(_detect_project_name(root), "my-pkg")

    def test_falls_back_to_directory_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(_detect_project_name(root), root.name)


class DetectEntryPointsTests(unittest.TestCase):
    def test_reads_project_scripts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pyproject.toml").write_text(
                "[project.scripts]\ngoverned = \"governancekit.cli:main\"\n",
                encoding="utf-8",
            )
            eps = _detect_entry_points(root)
            self.assertTrue(any("governed" in ep.description for ep in eps))

    def test_detects_main_py(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pkg = root / "mypkg"
            pkg.mkdir()
            (pkg / "__main__.py").write_text("", encoding="utf-8")
            eps = _detect_entry_points(root)
            self.assertTrue(any("python -m mypkg" in ep.description for ep in eps))


class RunMapTests(unittest.TestCase):
    def _make_project(self, root: Path) -> None:
        (root / "pyproject.toml").write_text(
            "[project]\nname = \"testproject\"\n", encoding="utf-8"
        )
        src = root / "testproject"
        src.mkdir()
        (src / "core.py").write_text(
            '"""Core module."""\n\ndef run(x, y):\n    """Run it."""\n    pass\n',
            encoding="utf-8",
        )

    def test_creates_output_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_project(root)
            result = run_map(root)
            self.assertTrue(result.output_path.is_file())

    def test_output_contains_project_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_project(root)
            result = run_map(root)
            content = result.output_path.read_text(encoding="utf-8")
            self.assertIn("testproject", content)

    def test_output_contains_symbol(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_project(root)
            result = run_map(root)
            content = result.output_path.read_text(encoding="utf-8")
            self.assertIn("run", content)

    def test_custom_output_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_project(root)
            out = root / "custom" / "map.md"
            result = run_map(root, output=out)
            self.assertEqual(result.output_path, out)
            self.assertTrue(out.is_file())

    def test_file_and_symbol_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_project(root)
            result = run_map(root)
            self.assertGreaterEqual(result.file_count, 1)
            self.assertGreaterEqual(result.symbol_count, 1)

    def test_codemap_not_in_own_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_project(root)
            result = run_map(root)
            content = result.output_path.read_text(encoding="utf-8")
            self.assertNotIn("codemap.md", content)

    def test_gitignore_excludes_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_project(root)
            (root / "secret.py").write_text("SECRET = 1\n", encoding="utf-8")
            (root / ".gitignore").write_text("secret.py\n", encoding="utf-8")
            result = run_map(root)
            paths = [str(f.path) for f in result.files]
            self.assertFalse(any("secret.py" in p for p in paths))


if __name__ == "__main__":
    unittest.main()
