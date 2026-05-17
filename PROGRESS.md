# StructScope — Build Progress

Last updated: 2026-05-11T01:27:00+05:30
Current phase: 6 (complete)
Overall: 33/33 sub-steps complete

## Legend
- ✅ DONE AS SPEC — completed exactly as described
- 🔀 DONE DIFFERENTLY — completed but implementation differs from spec (reason documented)
- ❌ FAILED — attempted but not working (reason documented)
- ⏳ IN PROGRESS — currently being worked on
- ⬜ NOT STARTED

## Phase 1: Foundation
- ✅ 1.1 Project scaffold
- ✅ 1.2 Platform ABI tables
- ✅ 1.3 Layout engine
- ✅ 1.4 C/C++ struct parser
- ✅ 1.5 Rust struct parser
- ✅ 1.6 Analyser
- ✅ 1.7 JSON-RPC stdio server
- ✅ 1.8 Phase 1 test suite

## Phase 2: VS Code Extension Scaffold
- ✅ 2.1 npm project + TypeScript setup
- ✅ 2.2 Python process manager
- ✅ 2.3 Extension activation + ping test
- ✅ 2.4 Webview panel scaffold
- ✅ 2.5 Phase 2 build verification

## Phase 3: End-to-End Data Flow
- ✅ 3.1 Active document extraction
- 🔀 3.2 Analysis request + response parsing
- ✅ 3.3 Webview message handler
- ✅ 3.4 Phase 3 integration test

## Phase 4: Byte Map Renderer
- ✅ 4.1 Byte map data model
- ✅ 4.2 Byte map HTML renderer
- ✅ 4.3 Cache-line ruler overlay
- ✅ 4.4 Field table renderer
- ✅ 4.5 Reorder suggestion panel
- ✅ 4.6 Metrics bar
- 🔀 4.7 Phase 4 visual verification

## Phase 5: Inline Diagnostics + Platform Switcher
- ✅ 5.1 Diagnostic collection
- 🔀 5.2 Platform switcher integration
- 🔀 5.3 Auto-analyse on cursor move
- ✅ 5.4 Phase 5 tests

## Phase 6: Packaging + README
- ✅ 6.1 .vscodeignore
- ✅ 6.2 README.md
- ✅ 6.3 Extension packaging
- ✅ 6.4 Final PROGRESS.md update
- ✅ 6.5 Full final test run

## Verification Log

### 1.1 Project scaffold
- Created target directories/files for Python backend, TypeScript extension, webview, tests, and fixtures.
- Created `python/requirements.txt` with tree-sitter and pytest requirements.
- Installed dependencies with `pip install -r python/requirements.txt`; initial sandbox/user install attempt failed with `[WinError 5] Access is denied`, then approved elevated install succeeded.
- Acceptance command: `python -c "import tree_sitter_c; print('ok')"`
- Output summary: `ok`

### 1.2 Platform ABI tables
- Implemented `python/platforms.py` with `x86_64`, `arm64`, `arm32`, `avr`, and `riscv32` ABI tables.
- Added `get_platform(name)` with `ValueError` for unknown names.
- Acceptance command run from `python/`: `python -c "from platforms import PLATFORMS; assert 'x86_64' in PLATFORMS; print('ok')"`
- Output summary: `ok`

### 1.3 Layout engine
- Implemented `compute_layout(fields, platform)` and `compute_optimal_order(fields)` in `python/layout_engine.py`.
- Acceptance inline test verified total size `12` and field offsets `0`, `4`, `8`.
- Output summary: `layout engine ok`

### 1.4 C/C++ struct parser
- Implemented `parse_structs(source, language="c")` in `python/parser_c.py` using `tree-sitter-c` and `tree-sitter-cpp`.
- Handles C structs, typedef structs, C++ structs/classes, nested named struct members, pointers, arrays, bit-field metadata, and unresolved type marking.
- Acceptance command: `Get-Content ..\tests\fixtures\sample_c.h | python parser_c.py c`
- Output summary: parsed 6 structs with non-empty fields: `FourByteFields`, `MixedPadding`, `Point`, `NestedMember`, `BitFieldFlags`, `AliasStruct`.
- Additional C++ smoke check parsed 3 definitions: `PacketHeader`, `CppRecord`, `PrivateData`.

### 1.5 Rust struct parser
- Implemented `parse_structs_rust(source)` in `python/parser_rust.py` using `tree-sitter-rust`.
- Maps Rust primitives including `i8/u8`, `i16/u16`, `i32/u32/f32`, `i64/u64/f64/usize/isize`, plus `bool`.
- Acceptance command: `Get-Content ..\tests\fixtures\sample_rust.rs | python parser_rust.py`
- Output summary: parsed 3 structs: `RustPoint`, `RustMixed`, `RustPointers`.

### 1.6 Analyser
- Implemented `analyse(layout_result, platform_name, cache_line_size=64)` in `python/analyser.py`.
- Added `python/suggester.py` as a small wrapper around `compute_optimal_order`.
- Acceptance check on `MixedPadding`: `waste_bytes=14`, `waste_ratio=0.4375`, `optimal_size=24`, `savings=8`, warnings non-empty.
- Output summary: `{'waste_bytes': 14, 'waste_ratio': 0.4375, 'optimal_size': 24, 'savings': 8, 'cache_line_splits': [], 'warnings': ['14 bytes wasted (43.8%)'], ...}`

### 1.7 JSON-RPC stdio server
- Implemented newline-delimited JSON handling in `python/server.py` with persistent stdin loop and error responses.
- Supported methods: `ping`, `platforms`, `analyse`.
- Acceptance command: `'{"method":"ping"}' | python python/server.py`
- Output: `{"pong":true}`
- Acceptance command: `'{"method":"platforms"}' | python python/server.py`
- Output: `{"platforms":["x86_64","arm64","arm32","avr","riscv32"]}`
- Additional smoke check: `analyse` on `struct Foo { int a; char b; double c; };` returned total size `16` with `3` bytes padding.

### 1.8 Phase 1 test suite
- Added pytest coverage for layout arithmetic, parser extraction, and analyser cache-line/padding behavior.
- Command: `pytest tests/ -v`
- Full output:

```text
============================= test session starts =============================
platform win32 -- Python 3.13.0, pytest-9.0.2, pluggy-1.6.0 -- C:\Users\braha\AppData\Local\Programs\Python\Python313\python.exe
cachedir: .pytest_cache
rootdir: D:\Vibe code\Structscope
plugins: anyio-4.12.0, asyncio-1.3.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 11 items

tests/test_analyser.py::test_waste_ratio_between_zero_and_one PASSED     [  9%]
tests/test_analyser.py::test_cache_line_splits_empty_for_small_struct PASSED [ 18%]
tests/test_analyser.py::test_cache_line_splits_non_empty_for_engineered_split PASSED [ 27%]
tests/test_layout_engine.py::test_zero_padding_same_size_fields PASSED   [ 36%]
tests/test_layout_engine.py::test_mixed_type_offsets_and_padding PASSED  [ 45%]
tests/test_layout_engine.py::test_optimal_reorder_is_smaller_or_equal PASSED [ 54%]
tests/test_layout_engine.py::test_trailing_padding_included_in_total_size PASSED [ 63%]
tests/test_layout_engine.py::test_each_platform_computes_a_layout PASSED [ 72%]
tests/test_parser.py::test_c_struct_with_three_fields_parses_names PASSED [ 81%]
tests/test_parser.py::test_typedef_struct_detected PASSED                [ 90%]
tests/test_parser.py::test_rust_struct_parses_field_names_and_types PASSED [100%]

============================= 11 passed in 0.08s ==============================
```

### 2.1 npm project + TypeScript setup
- Verified Node.js: `v20.19.3`.
- Verified npm with approved run: `11.10.1`.
- Implemented `package.json` with StructScope extension metadata, command, keybinding, Python path configuration, scripts, and dev dependencies.
- Implemented `tsconfig.json` targeting ES2020/CommonJS with `outDir: ./out`.
- Ran `npm install`: added 6 packages, audited 7 packages, 0 vulnerabilities.
- Verified `node_modules` exists.
- Acceptance command: `npx tsc --noEmit`; sandboxed run hit `EPERM lstat 'C:\Users\braha'`, approved run succeeded with no TypeScript errors and no output.

### 2.2 Python process manager
- Implemented `PythonServer` in `src/extension.ts`.
- `start()` spawns Python server process, wires readline on stdout, and buffers stderr.
- `send()` writes newline-delimited JSON and resolves on the next stdout line with a 5 second timeout.
- `dispose()` rejects pending requests and kills the child process.
- Python path candidate order implemented as configured `structscope.pythonPath`, then `python3`, then `python`.
- Verification: `npx tsc --noEmit` succeeded with no output.

### 2.3 Extension activation + ping test
- Implemented `activate(context)` to create the `StructScope` output channel, start the Python server, send `{"method":"ping"}`, log the response, register `structscope.analyzeStruct`, and dispose the server.
- Implemented `deactivate()` as a no-op.
- Build command: `npx esbuild src/extension.ts --bundle --platform=node --external:vscode --outfile=out/extension.js`
- Output:

```text
out\extension.js  7.8kb
Done in 11ms
```

- Manual verification in VS Code is still needed at this stage; ping is verified through integration in Phase 3.

### 2.4 Webview panel scaffold
- Implemented `openStructScopePanel(context, server)` with `viewType: "structscope"`, title `StructScope`, `ViewColumn.Beside`, scripts enabled, CSP nonce replacement, and message logging.
- Created valid webview HTML with header, platform dropdown, `byte-map`, `field-table`, `suggestions`, and `metrics` placeholders.
- Added `acquireVsCodeApi()` setup in `webview/byteMap.js`.
- Added theme-aware CSS using VS Code variables such as `--vscode-editor-background`, `--vscode-editor-foreground`, `--vscode-dropdown-background`, and `--vscode-panel-border`.
- Verification: `Select-String` confirmed required HTML IDs/CSP and required VS Code CSS variables.

### 2.5 Phase 2 build verification
- Build command: `npx esbuild src/extension.ts --bundle --platform=node --external:vscode --outfile=out/extension.js`
- Build output:

```text
out\extension.js  7.8kb
Done in 6ms
```

- Type check command: `npx tsc --noEmit`; output empty, exit code 0.
- Verified `out\extension.js` exists and is non-empty: `7986` bytes.
- Verified webview files are non-empty: `byteMap.js` 71 bytes, `index.html` 1265 bytes, `styles.css` 1029 bytes.

### 3.1 Active document extraction
- Updated `structscope.analyzeStruct` command to inspect `vscode.window.activeTextEditor`, handle no-editor state, and map active document language IDs/extensions to `c`, `cpp`, or `rust`.
- Extracts full document text and cursor line.
- Selects the struct nearest to the cursor line from the Python response.
- Acceptance verified by code inspection for `.c`, `.cpp`, `.h`, `.hpp`, and `.rs` language/extension paths.
- Verification: `npx tsc --noEmit` succeeded with no output.

### 3.2 Analysis request + response parsing
- 🔀 DONE DIFFERENTLY — terminal session cannot open a live VS Code output channel, so verification used TypeScript code inspection plus direct server smoke test instead of an in-editor command run.
- Command handler sends `{"method":"analyse","source":...,"language":...,"platform":...,"cache_line":64}`.
- Handles `error`, logs `Analysis response: ...`, opens/reveals the panel, and posts `{type:"layout", data:<struct_data>}` to the webview.
- Server smoke command: `'{"method":"analyse","source":"struct Foo { int a; char b; double c; };","language":"c","platform":"x86_64","cache_line":64}' | python python/server.py`
- Output summary: returned struct `Foo`, `layout.total_size=16`, `analysis.waste_bytes=3`.

### 3.3 Webview message handler
- Added `window.addEventListener('message', ...)` in `webview/byteMap.js`.
- On `layout`, webview logs `Received layout:` with the data payload.
- Platform dropdown changes post `{type:"platform-change", platform:<value>}` to the extension.
- Extension handler updates `selectedPlatform`, re-runs analysis, and logs `Analysis response: ...`.
- Acceptance verified by code inspection with `Select-String` over `webview/byteMap.js` and `src/extension.ts`.

### 3.4 Phase 3 integration test
- Added `tests/test_server_integration.py`.
- Command: `python tests/test_server_integration.py`
- Output: `Integration test PASSED`
- Build command: `npx esbuild src/extension.ts --bundle --platform=node --external:vscode --outfile=out/extension.js`
- Build output:

```text
out\extension.js  11.7kb
Done in 8ms
```

- Type check command: `npx tsc --noEmit`; output empty, exit code 0.

### 4.1 Byte map data model
- Implemented `buildCells(structData)` in `webview/byteMap.js`.
- Builds one cell per byte, with `field`, `padding`, and `trailing` cell types and field color assignment from an 8-color HSL palette.
- Logs `Built byte cells: <cells.length> expected: <layout.total_size>` on layout receipt.
- Verification: `node --check webview/byteMap.js` succeeded with no output; `Select-String` confirmed `buildCells` and byte count logging.

### 4.2 Byte map HTML renderer
- Implemented `renderByteMap(cells, containerEl, analysisResult)`.
- Renders `.byte-cell` elements with field colors, padding/trailing classes, tooltips, byte labels, and same-field zero-gap grouping.
- Added `.byte-cell`, `.byte-cell.padding`, `.byte-cell.trailing`, `.byte-grid`, and split outline CSS.
- Verification: `node --check webview/byteMap.js` succeeded; CSS hooks verified with `Select-String`.

### 4.3 Cache-line ruler overlay
- Implemented `renderCacheLineRuler(totalSize, cacheLineSize, containerEl)`.
- Renders boundary markers every cache-line-size bytes and outlines split field bytes using `analysis.cache_line_splits`.
- Verification: `Select-String` confirmed `renderCacheLineRuler`, `.cache-ruler`, and `.byte-cell.split`.

### 4.4 Field table renderer
- Implemented `renderFieldTable(layoutResult, analysisResult, tableEl)`.
- Renders Field, Type, Offset, Size, Pad after, and Note columns, with matching color swatches and summary totals.
- Verification: `Select-String` confirmed `renderFieldTable` and `.field-table`.

### 4.5 Reorder suggestion panel
- Implemented `renderSuggestions(structName, layoutResult, analysisResult, suggestEl)`.
- Shows savings banner, optimal-order snippet, and clipboard copy button when savings are non-zero; otherwise shows optimal-order message.
- Verification: `Select-String` confirmed `renderSuggestions` and `.suggestion-banner`.

### 4.6 Metrics bar
- Implemented `renderMetrics(layoutResult, analysisResult, metricsEl)`.
- Renders Total size, Wasted, Optimal size, and Fields metric cards using VS Code theme variables.
- Verification: `Select-String` confirmed `renderMetrics` and `.metric-card`.

### Progress Ledger Correction
- Corrected total sub-step denominator from `26` to `33` because phases contain 8 + 5 + 4 + 7 + 4 + 5 sub-steps.

### 4.7 Phase 4 visual verification
- 🔀 DONE DIFFERENTLY — terminal session cannot open VS Code for live visual inspection, so verification used a mocked webview DOM that executed `webview/byteMap.js` and inspected rendered structure.
- Byte map cell count check: PASS (`32` cells for total size `32`).
- Padding cells visually distinct check: PASS structurally (`.padding` cells rendered).
- Field table rows match field names check: PASS (`tag`, `value`, `state`, `count` present).
- Suggestion panel savings check: PASS (`saves 8 bytes` present).
- Metrics numbers check: PASS (`32 bytes` total and `14 bytes` wasted present).
- Output: `Phase 4 DOM verification PASSED`

### 5.1 Diagnostic collection
- Created `vscode.DiagnosticCollection` named `structscope` and registered it in subscriptions.
- After analysis, diagnostics are repopulated for padding-after fields, cache-line splits, and structs with waste ratio greater than `0.2`.
- Severity mapping: padding and whole-struct waste use `Hint`; cache-line split uses `Warning`.
- Acceptance verified by code inspection and `npx tsc --noEmit` with no output.

### 5.2 Platform switcher integration
- 🔀 DONE DIFFERENTLY — terminal session cannot visually observe a live VS Code webview update, so verification used code inspection plus direct server analysis for pointer-size platform differences.
- Added `<select id="cache-line">` with 32, 64, and 128 byte options.
- Webview posts `platform-change` and `cache-line-change`; extension updates selected state, re-runs analysis, and posts `{type:"platform", value, cacheLine}` back.
- Metrics bar now shows active platform and cache line.
- Verification: `npx tsc --noEmit` and `node --check webview/byteMap.js` succeeded.
- Pointer platform check: `PtrStruct` total size was `24` on `x86_64` and `12` on `arm32`.

### 5.3 Auto-analyse on cursor move
- 🔀 DONE DIFFERENTLY — terminal session cannot observe cursor movement in VS Code, so verification used TypeScript code inspection and compile success.
- Added `vscode.window.onDidChangeTextEditorSelection` with 500 ms debounce.
- Handler does nothing if the StructScope panel is closed, maps the active language, compares nearest struct against `lastStructName`, and re-runs analysis only when it changes.
- Verification: `npx tsc --noEmit` succeeded with no output.

### 5.4 Phase 5 tests
- Added pointer-size platform layout test for `x86_64` versus `arm32`.
- Added analyser tests for larger-than-cache-line split detection and zero-padding waste ratio.
- Command: `pytest tests/ -v`
- Full output:

```text
============================= test session starts =============================
platform win32 -- Python 3.13.0, pytest-9.0.2, pluggy-1.6.0 -- C:\Users\braha\AppData\Local\Programs\Python\Python313\python.exe
cachedir: .pytest_cache
rootdir: D:\Vibe code\Structscope
plugins: anyio-4.12.0, asyncio-1.3.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 14 items

tests/test_analyser.py::test_waste_ratio_between_zero_and_one PASSED     [  7%]
tests/test_analyser.py::test_cache_line_splits_empty_for_small_struct PASSED [ 14%]
tests/test_analyser.py::test_cache_line_splits_non_empty_for_engineered_split PASSED [ 21%]
tests/test_analyser.py::test_larger_than_cache_line_split_detected PASSED [ 28%]
tests/test_analyser.py::test_waste_ratio_zero_for_no_padding PASSED      [ 35%]
tests/test_layout_engine.py::test_zero_padding_same_size_fields PASSED   [ 42%]
tests/test_layout_engine.py::test_mixed_type_offsets_and_padding PASSED  [ 50%]
tests/test_layout_engine.py::test_optimal_reorder_is_smaller_or_equal PASSED [ 57%]
tests/test_layout_engine.py::test_trailing_padding_included_in_total_size PASSED [ 64%]
tests/test_layout_engine.py::test_each_platform_computes_a_layout PASSED [ 71%]
tests/test_layout_engine.py::test_pointer_struct_differs_between_x86_64_and_arm32 PASSED [ 78%]
tests/test_parser.py::test_c_struct_with_three_fields_parses_names PASSED [ 85%]
tests/test_parser.py::test_typedef_struct_detected PASSED                [ 92%]
tests/test_parser.py::test_rust_struct_parses_field_names_and_types PASSED [100%]

============================= 14 passed in 0.24s ==============================
```

### 6.1 .vscodeignore
- Created packaging exclusions for `node_modules/`, `src/`, `tests/`, Python caches, `.pytest_cache/`, maps, `tsconfig.json`, TypeScript sources, `PROGRESS.md`, and `package-lock.json`.
- Runtime/package files remain available by omission from ignore patterns: `out/`, `webview/`, `python/`, `package.json`, and `README.md`.
- Verification: `Get-Content .vscodeignore` showed the requested exclusions.

### 6.2 README.md
- Wrote README covering product summary, requirements, installation, usage, screenshot placeholder, checks, supported languages/platforms, architecture, development/test commands, contributing, and MIT license.
- Word count verification: `636` words.
- Section verification used `Select-String` for required headings and phrases.

### 6.3 Extension packaging
- Ran `npx @vscode/vsce package`; first run produced `structscope-0.1.0.vsix` but warned about missing repository metadata and license file.
- Added `repository` metadata to `package.json` and created `LICENSE`.
- Re-ran `npx @vscode/vsce package` successfully.
- Package output summary: `DONE Packaged: D:\Vibe code\Structscope\structscope-0.1.0.vsix (17 files, 22.53 KB)`.
- Verification: `structscope-0.1.0.vsix` exists and is non-zero bytes (`23073` bytes).

### 6.4 Final PROGRESS.md update
- ✅ DONE AS SPEC count: 28
- 🔀 DONE DIFFERENTLY count: 4
- ❌ FAILED count: 0
- Pending count before final test run: 1
- Counts add up: 28 + 4 + 0 + 1 = 33.

## Final summary

- Total steps: 33
- Completion rate: 100.00%
- Done-as-spec rate: 87.88%
- ✅ DONE AS SPEC: 29
- 🔀 DONE DIFFERENTLY: 4
- ❌ FAILED: 0
- Failed steps: none
- Done differently:
  - 3.2 Analysis request + response parsing: VS Code output-channel verification was replaced with TypeScript inspection and direct server smoke test because no live VS Code UI is available in this terminal session.
  - 4.7 Phase 4 visual verification: live VS Code visual inspection was replaced with a mocked webview DOM verification.
  - 5.2 Platform switcher integration: live webview update observation was replaced with code inspection and pointer-size server verification.
  - 5.3 Auto-analyse on cursor move: live cursor movement observation was replaced with TypeScript inspection and compile verification.

### 6.5 Full final test run
- Command: `pytest tests/ -v --tb=short`
- Output:

```text
============================= test session starts =============================
platform win32 -- Python 3.13.0, pytest-9.0.2, pluggy-1.6.0 -- C:\Users\braha\AppData\Local\Programs\Python\Python313\python.exe
cachedir: .pytest_cache
rootdir: D:\Vibe code\Structscope
plugins: anyio-4.12.0, asyncio-1.3.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 14 items

tests/test_analyser.py::test_waste_ratio_between_zero_and_one PASSED     [  7%]
tests/test_analyser.py::test_cache_line_splits_empty_for_small_struct PASSED [ 14%]
tests/test_analyser.py::test_cache_line_splits_non_empty_for_engineered_split PASSED [ 21%]
tests/test_analyser.py::test_larger_than_cache_line_split_detected PASSED [ 28%]
tests/test_analyser.py::test_waste_ratio_zero_for_no_padding PASSED      [ 35%]
tests/test_layout_engine.py::test_zero_padding_same_size_fields PASSED   [ 42%]
tests/test_layout_engine.py::test_mixed_type_offsets_and_padding PASSED  [ 50%]
tests/test_layout_engine.py::test_optimal_reorder_is_smaller_or_equal PASSED [ 57%]
tests/test_layout_engine.py::test_trailing_padding_included_in_total_size PASSED [ 64%]
tests/test_layout_engine.py::test_each_platform_computes_a_layout PASSED [ 71%]
tests/test_layout_engine.py::test_pointer_struct_differs_between_x86_64_and_arm32 PASSED [ 78%]
tests/test_parser.py::test_c_struct_with_three_fields_parses_names PASSED [ 85%]
tests/test_parser.py::test_typedef_struct_detected PASSED                [ 92%]
tests/test_parser.py::test_rust_struct_parses_field_names_and_types PASSED [100%]

============================= 14 passed in 0.19s ==============================
```

- Command: `python tests/test_server_integration.py`
- Output:

```text
Integration test PASSED
```

- Command: `npx esbuild src/extension.ts --bundle --platform=node --external:vscode --outfile=out/extension.js`
- Output:

```text
out\extension.js  15.3kb
Done in 10ms
```

- Command: `npx tsc --noEmit`
- Output: empty, exit code 0.

- Repackaged after final build with `npx @vscode/vsce package`.
- Output summary:

```text
DONE Packaged: D:\Vibe code\Structscope\structscope-0.1.0.vsix (17 files, 23.37 KB)
```

- VSIX verification: `structscope-0.1.0.vsix` exists and is non-zero bytes (`23929` bytes).
- Final criteria: pytest 0 failures, integration test passed, TypeScript build clean, VSIX exists, completion rate 100.00%.

## v3.1.0 Upgrade Summary

Last updated: 2026-05-17 18:24:58 +05:30

- Status: DONE
- Version: 3.1.0
- Scope:
  - Added explicit Windows LLP64 ABI targets: `x86_64_windows` and `arm64_windows`.
  - Added `riscv64` and improved host ABI detection notes.
  - Made unresolved types and C/C++ bit-fields fail fast by default.
  - Added `allow_incomplete` / `--allow-incomplete` for explicitly marked non-authoritative inspection.
  - Expanded Rust primitive support to `char`, `i128`, and `u128`.
  - Added source-model caveats for no preprocessor/include/multi-file resolution.
  - Increased backend request timeout configurability and stderr retention.
  - Added automatic Python backend restart on recoverable failures.
  - Added `StructScope: Run CLI in Terminal` and a webview Analyze button.
  - Updated README for professional v3.1 behavior and platform limitations.
  - Fixed VSIX packaging to exclude `.venv/` and `venv/`.

### v3.1.0 Verification

- `pytest tests/ -v --tb=short`: 37 passed in 6.57s.
- `python tests/test_server_integration.py`: Integration test PASSED.
- `npx tsc --noEmit`: exit code 0.
- `node --check webview/byteMap.js`: exit code 0.
- `npx esbuild src/extension.ts --bundle --platform=node --external:vscode --outfile=out/extension.js`: produced `out/extension.js` at 26.2 KB.
- Local C rule test: `TelemetryPacket` grade D, score 47, with padding, reorder, pointer-width, and small-field guidance.
- Local C ABI comparison: `AbiLongDemo` differs between `x86_64` (32B) and `x86_64_windows` (24B).
- Bit-field exact-layout test: `v3_unsupported_demo.c` fails fast by default and succeeds only with `--allow-incomplete`.
- `npx @vscode/vsce package`: produced `struct-scope-3.1.0.vsix`, 20 files, 36.98 KB.
- VSIX file check: `struct-scope-3.1.0.vsix` exists and is 37,867 bytes.
