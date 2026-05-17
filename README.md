# Struct Scope

Struct Scope is a local-first Visual Studio Code extension and command-line tool for inspecting memory layout in C, C++, and Rust. It parses source files, extracts struct-like definitions, computes ABI-aware field placement, and reports byte offsets, field sizes, alignment, padding, cache-line split risks, platform differences, and rule-based improvement guidance without invoking a compiler.

The project is designed for systems programming, embedded development, performance engineering, protocol design, and low-level code review workflows where object layout affects memory footprint, binary compatibility, cache behavior, or wire-format design.

## Capabilities

- Static analysis for C structs, C++ structs/classes with data members, and Rust structs
- ABI-aware layout computation for Unix-like LP64, Windows LLP64, 32-bit, embedded, and RISC-V targets
- Host Python ABI auto-detection with manual target-platform override for compiler and cross-compilation targets
- Visual byte map with field regions, padding cells, and cache-line boundaries
- Field table with offsets, sizes, padding-after values, and cache-line notes
- Rule-based, local-only improvement guidance with severity, confidence, and safe recommendations
- Layout score and grade for quick prioritization
- Greedy field reorder suggestions with expected byte savings
- Platform comparison reports for pointer-width and ABI-sensitive structures
- VS Code diagnostics for padding hotspots, high-waste structs, and cache-line split fields
- Analyze-on-save workflow with optional automatic dashboard opening
- Activity Bar dashboard, status bar command, editor title actions, context menu actions, webview Analyze button, and Command Palette commands
- Terminal CLI for scripting, CI checks, JSON output, Markdown reports, and platform comparison

## Safety Model

Struct Scope provides rule-based suggestions only. It does not rewrite source code automatically, execute generated code, fetch remote rules, or call model APIs. Every recommendation is returned with `safe: true` and `auto_apply: false`; the user remains responsible for deciding whether a layout change is compatible with ABI, serialization, protocol, or public API requirements.

Exact analysis fails fast by default when a field type cannot be resolved or a C/C++ bit-field would require compiler-specific packing rules. Partial inspection is available through the `--allow-incomplete` CLI flag or `structscope.allowIncompleteLayouts`, but those results are explicitly marked non-authoritative.

## Requirements

- Visual Studio Code 1.85 or newer
- Python 3.8 or newer
- `pip`
- Node.js and npm for development, testing, or packaging

Install Python dependencies:

```sh
pip install -r python/requirements.txt
```

## VS Code Usage

Open a supported C, C++, header, or Rust source file. Struct Scope can be invoked through:

- File save when `structscope.analyzeOnSave` is enabled
- `StructScope: Analyze Struct` from the Command Palette
- `Ctrl+Shift+M` on Windows/Linux or `Cmd+Shift+M` on macOS
- The Struct Scope status bar item
- The editor title action or editor context menu
- The Struct Scope Activity Bar dashboard
- `StructScope: Run CLI in Terminal`, which opens a VS Code terminal and runs the local CLI against the active file

The dashboard renders the selected structure as a byte map, field table, metrics panel, rule insights panel, cache-line ruler, and reorder suggestion panel. The platform selector can be changed manually. The Detect control re-runs host ABI detection and refreshes the layout.

## Terminal Usage

Analyze a source file:

```sh
python python/cli.py tests/fixtures/v2_local_demo.c --platform x86_64
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
python python/cli.py tests/fixtures/v2_local_demo.c --compare x86_64 x86_64_windows arm32
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

Example local C output:

```text
TelemetryPacket: total=40B padding=18B (45.0%) optimal=24B savings=16B
CacheSplitDemo: total=68B padding=0B (0.0%) optimal=68B savings=0B
warning: Field value straddles cache line boundary
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

## Supported Inputs

Languages:

- C structs
- C++ structs and classes with data members
- Rust structs

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

## Architecture

Struct Scope is split into a TypeScript VS Code extension and a Python analysis backend.

- `src/extension.ts` manages VS Code commands, diagnostics, status bar state, Activity Bar entries, the webview, and the Python child process.
- `python/server.py` exposes newline-delimited JSON-RPC over stdio.
- `python/cli.py` provides terminal access to the same analysis pipeline.
- `python/parser_c.py` and `python/parser_rust.py` extract structure definitions with tree-sitter.
- `python/layout_engine.py` computes ABI layout with deterministic alignment arithmetic.
- `python/analyser.py` and `python/rules_engine.py` compute waste, cache-line risks, layout grade, and safe guidance.
- `python/platforms.py` contains ABI tables and host platform detection.
- `webview/` contains the local dashboard UI assets.

No source code is sent to cloud services, telemetry endpoints, compiler services, third-party analysis systems, or model APIs.

## Development

Run tests:

```sh
pytest tests/ -v
python tests/test_server_integration.py
```

Run TypeScript checks and build:

```sh
npx tsc --noEmit
npx esbuild src/extension.ts --bundle --platform=node --external:vscode --outfile=out/extension.js
```

The test suite includes backend arithmetic, parser coverage, CLI behavior, server integration, static checks for save/selection-triggered VS Code wiring, and static checks for dashboard controls. Manual VS Code smoke testing is still useful before publishing a release, but the expected entry points are covered by automated repository checks.

Package the extension:

```sh
npx @vscode/vsce package
```

## License

MIT
