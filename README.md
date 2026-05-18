# Struct Scope

Struct Scope is a local-first Visual Studio Code extension and command-line tool for inspecting memory layout in C, C++, and Rust. It parses source files, extracts struct-like definitions, computes ABI-aware field placement, and reports byte offsets, field sizes, alignment, padding, cache-line split risks, platform differences, and rule-based improvement guidance without invoking a compiler.

The project is designed for systems programming, embedded development, performance engineering, protocol design, and low-level code review workflows where object layout affects memory footprint, binary compatibility, cache behavior, or wire-format design.

## Capabilities

- Static analysis for C structs, C++ structs/classes with data members, and Rust structs.
- ABI-aware layout computation for Unix-like LP64, Windows LLP64, 32-bit, embedded, and RISC-V targets.
- Host Python ABI detection with manual target-platform override for compiler and cross-compilation targets.
- Visual byte map with field regions, padding cells, cache-line boundaries, field table, metrics, and reorder suggestions.
- Rule-based, local-only improvement guidance with severity, confidence, and safe recommendations.
- VS Code diagnostics for padding hotspots, high-waste structs, incomplete layouts, and cache-line split fields.
- Analyze-on-save workflow with optional automatic dashboard opening.
- Activity Bar dashboard, status bar command, editor title actions, context menu actions, webview Analyze button, and Command Palette commands.
- Terminal CLI for scripting, CI checks, JSON output, Markdown reports, and platform comparison.

## Safety Model

Struct Scope provides rule-based suggestions only. It does not rewrite source code automatically, execute generated code, fetch remote rules, or call model APIs. Recommendations are returned with `safe: true` and `auto_apply: false`; users remain responsible for deciding whether a layout change is compatible with ABI, serialization, protocol, or public API requirements.

Exact analysis fails fast by default when a field type cannot be resolved or a C/C++ bit-field would require compiler-specific packing rules. Partial inspection is available through the `--allow-incomplete` CLI flag or `structscope.allowIncompleteLayouts`, but those results are explicitly marked non-authoritative.

## Requirements

- Visual Studio Code 1.85 or newer.
- Python 3.8 or newer.
- Node.js and npm for development, testing, or packaging.

The extension checks for its Python parser dependencies on activation. If `tree-sitter` packages are missing and `structscope.autoInstallPythonDeps` is enabled, Struct Scope runs `python -m pip install -r python/requirements.txt` for the selected Python executable. Environments without network access can install dependencies manually:

```sh
pip install -r python/requirements.txt
```

## VS Code Usage

Open a supported C, C++, header, or Rust source file. Struct Scope can be invoked through:

- `StructScope: Analyze Struct` from the Command Palette.
- `Ctrl+Shift+M` on Windows/Linux or `Cmd+Shift+M` on macOS.
- The Struct Scope status bar item.
- The editor title action or editor context menu.
- The Struct Scope Activity Bar dashboard.
- The webview `Analyze` button.
- `StructScope: Run CLI in Terminal`, which opens a VS Code terminal and runs the local CLI against the active file.
- File save when `structscope.analyzeOnSave` is enabled.

The dashboard renders the selected structure as a byte map, field table, metrics panel, rule insights panel, cache-line ruler, and reorder suggestion panel. The platform selector can be changed manually. The Detect control re-runs host ABI detection and refreshes the layout.

## Terminal Usage

Analyze a source file:

```sh
python python/cli.py tests/fixtures/v2_local_demo.c --platform x86_64
```

Analyze a local file and print JSON:

```sh
python python/cli.py testing.c --platform x86_64 --json
```

Filter output to one struct:

```sh
python python/cli.py tests/fixtures/v2_local_demo.c --platform x86_64 --struct TelemetryPacket
```

Print rule guidance only:

```sh
python python/cli.py tests/fixtures/v2_local_demo.c --platform x86_64 --struct TelemetryPacket --rules-only
```

Compare target platforms:

```sh
python python/cli.py tests/fixtures/v3_abi_demo.c --compare x86_64 x86_64_windows --struct AbiLongDemo
```

Emit JSON or Markdown reports:

```sh
python python/cli.py tests/fixtures/v2_local_demo.c --platform auto --json
python python/cli.py tests/fixtures/v2_local_demo.c --platform x86_64 --markdown
```

Inspect a partial, non-authoritative layout when unsupported fields are present:

```sh
python python/cli.py path/to/file.c --allow-incomplete --json
```

## Configuration

| Setting | Description |
| --- | --- |
| `structscope.pythonPath` | Optional Python executable path for the analysis backend |
| `structscope.defaultPlatform` | Default ABI platform. `auto` detects the host Python ABI; explicit targets include `x86_64`, `x86_64_windows`, `arm64`, `arm64_windows`, `arm32`, `avr`, `riscv32`, and `riscv64` |
| `structscope.cacheLine` | Cache-line size in bytes: 32, 64, or 128 |
| `structscope.analyzeOnSave` | Runs analysis when supported files are saved |
| `structscope.autoOpenPanel` | Opens the dashboard automatically during save-triggered analysis |
| `structscope.showStatusBar` | Shows or hides the Struct Scope status bar command |
| `structscope.allowIncompleteLayouts` | Allows non-authoritative partial layouts for unresolved types or bit-fields. Disabled by default |
| `structscope.requestTimeoutMs` | Python backend request timeout in milliseconds. Default: 15000 |
| `structscope.autoInstallPythonDeps` | Installs missing Python parser dependencies automatically. Enabled by default |

## Supported Inputs

Languages:

- C structs.
- C++ structs and classes with data members.
- Rust structs.

ABI platforms:

- `x86_64`
- `x86_64_windows`
- `arm64`
- `arm64_windows`
- `arm32`
- `avr`
- `riscv32`
- `riscv64`

The `x86_64` and `arm64` targets model Unix-like LP64 ABIs where `long` is 8 bytes. The `x86_64_windows` and `arm64_windows` targets model Windows LLP64 ABIs where `long` remains 4 bytes and pointers are 8 bytes. The `auto` platform option detects the host Python ABI only. Cross-compilation targets, MSVC versus non-MSVC ABI choices, embedded compiler flags, and project-specific packing pragmas cannot be inferred reliably from source text alone, so projects should select the intended target ABI explicitly.

Struct Scope analyzes source text as provided to tree-sitter. It does not run the C/C++ preprocessor, expand macros, load include files, or resolve symbols across translation units. Dependent type definitions must be included in the analyzed text or the layout will fail fast as incomplete.

C/C++ bit-fields are detected and reported as unsupported for exact layout because packing depends on compiler, target, declaration type, and flags. Use the target compiler as the source of truth for externally visible bit-field layouts.

## Development

Install dependencies:

```sh
npm install
pip install -r python/requirements.txt
```

Run tests:

```sh
pytest tests/ -v
python tests/test_server_integration.py
```

Run TypeScript checks and build:

```sh
npm run compile
npm run build
```

Package the extension:

```sh
npm run package
```

The test suite includes backend arithmetic, parser coverage, CLI behavior, server integration, manifest checks, static checks for save/selection-triggered VS Code wiring, and static checks for dashboard controls. Manual VS Code smoke testing is still useful before publishing a release, but the expected entry points are covered by automated repository checks.

## License

MIT
