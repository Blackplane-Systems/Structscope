import * as childProcess from 'child_process';
import * as fs from 'fs';
import * as path from 'path';
import * as readline from 'readline';
import * as vscode from 'vscode';

type PendingRequest = {
  resolve: (value: object) => void;
  reject: (reason: Error) => void;
  timeout: NodeJS.Timeout;
};

type SupportedLanguage = 'c' | 'cpp' | 'rust';

type StructAnalysis = {
  name: string;
  line: number;
  fields?: AnalysisField[];
  layout: LayoutResult;
  analysis: AnalysisResult;
};

type AnalysisField = {
  name: string;
  raw_type?: string;
  type?: string;
  size: number;
  alignment: number;
  line?: number;
  offset?: number;
  padding_after?: number;
  unresolved?: boolean;
  bit_width?: number;
};

type LayoutResult = {
  fields: AnalysisField[];
  total_size: number;
  total_padding: number;
  alignment: number;
};

type AnalysisResult = {
  waste_bytes: number;
  waste_ratio: number;
  optimal_size: number;
  savings: number;
  cache_line_splits: Array<{ field_name: string; offset: number; size: number; line_size: number }>;
  warnings: string[];
  optimal_order?: AnalysisField[];
  layout_complete?: boolean;
  blockers?: Array<{ kind: string; struct: string; field: string; message: string; line?: number }>;
  rules?: Array<{ id: string; severity: string; title: string; message: string; recommendation: string; fields?: string[] }>;
  layout_score?: number;
  layout_grade?: string;
};

type AnalyseResponse = {
  structs?: StructAnalysis[];
  error?: string;
  platform?: string;
  requested_platform?: string;
  cache_line?: number;
};

type DetectPlatformResponse = {
  platform?: string;
  machine?: string;
  system?: string;
  pointer_size?: number;
  abi?: string;
  warning?: string;
  source?: string;
  error?: string;
};

type AnalysisContext = {
  uri: vscode.Uri;
  source: string;
  language: SupportedLanguage;
  cursorLine: number;
};

type StructScopeSettings = {
  defaultPlatform: string;
  cacheLine: number;
  analyzeOnSave: boolean;
  autoOpenPanel: boolean;
  showStatusBar: boolean;
  allowIncompleteLayouts: boolean;
  requestTimeoutMs: number;
  autoInstallPythonDeps: boolean;
};

export class PythonServer {
  private proc?: childProcess.ChildProcessWithoutNullStreams;
  private rl?: readline.Interface;
  private pending: PendingRequest[] = [];
  private stderrBuffer = '';
  private pythonPath?: string;
  private serverScript?: string;
  private starting?: Promise<void>;
  private disposed = false;
  private readonly stderrLimit = 65536;

  async start(pythonPath: string, serverScript: string): Promise<void> {
    this.pythonPath = pythonPath;
    this.serverScript = serverScript;
    this.disposed = false;
    await this.startProcess();
  }

  async restart(): Promise<void> {
    if (!this.pythonPath || !this.serverScript) {
      throw new Error('Python server paths are not configured');
    }
    this.stopProcess(new Error('Python server restarting'));
    await this.startProcess();
  }

  async send(request: object, timeoutMs = 15000): Promise<object> {
    if (!this.isRunning()) {
      await this.restart();
    }

    try {
      return await this.sendOnce(request, timeoutMs);
    } catch (error) {
      if (this.isRecoverable(error)) {
        await this.restart();
        return this.sendOnce(request, timeoutMs);
      }
      throw error;
    }
  }

  dispose(): void {
    this.disposed = true;
    this.stopProcess(new Error('Python server disposed'));
  }

  private startProcess(): Promise<void> {
    if (this.disposed) {
      return Promise.reject(new Error('Python server is disposed'));
    }
    if (this.isRunning()) {
      return Promise.resolve();
    }
    if (this.starting) {
      return this.starting;
    }
    if (!this.pythonPath || !this.serverScript) {
      return Promise.reject(new Error('Python server paths are not configured'));
    }

    const starting = new Promise<void>((resolve, reject) => {
      const pythonPath = this.pythonPath!;
      const serverScript = this.serverScript!;
      this.stderrBuffer = '';
      let settled = false;

      const proc = childProcess.spawn(pythonPath, [serverScript], {
        cwd: path.dirname(path.dirname(serverScript)),
        stdio: ['pipe', 'pipe', 'pipe']
      });
      this.proc = proc;

      const failStart = (error: Error) => {
        if (settled) {
          return;
        }
        settled = true;
        this.proc = undefined;
        reject(error);
      };

      proc.once('error', failStart);
      proc.once('spawn', () => {
        if (settled) {
          return;
        }
        settled = true;
        proc.off('error', failStart);
        this.rl = readline.createInterface({ input: proc.stdout });
        this.rl.on('line', (line) => this.handleLine(line));
        proc.stderr.on('data', (chunk: Buffer) => {
          this.stderrBuffer += chunk.toString('utf8');
          if (this.stderrBuffer.length > this.stderrLimit) {
            this.stderrBuffer = this.stderrBuffer.slice(-this.stderrLimit);
          }
        });
        proc.once('exit', (code, signal) => {
          if (this.proc === proc) {
            this.proc = undefined;
            this.rl?.close();
            this.rl = undefined;
          }
          this.rejectAll(new Error(`Python server exited (${code ?? signal ?? 'unknown'}): ${this.stderrBuffer}`));
        });
        resolve();
      });
    });
    this.starting = starting.finally(() => {
      this.starting = undefined;
    });
    return this.starting;
  }

  private sendOnce(request: object, timeoutMs: number): Promise<object> {
    if (!this.proc || !this.proc.stdin.writable) {
      return Promise.reject(new Error('Python server is not running'));
    }

    return new Promise((resolve, reject) => {
      const pending: PendingRequest = {
        resolve,
        reject,
        timeout: setTimeout(() => {
          this.removePending(pending);
          reject(new Error(`Python server request timed out after ${timeoutMs}ms. stderr: ${this.stderrBuffer}`));
        }, timeoutMs)
      };
      this.pending.push(pending);
      this.proc!.stdin.write(`${JSON.stringify(request)}\n`, 'utf8', (error) => {
        if (error) {
          this.removePending(pending);
          reject(error);
        }
      });
    });
  }

  private stopProcess(error: Error): void {
    this.rejectAll(error);
    this.rl?.close();
    this.proc?.kill();
    this.proc = undefined;
    this.rl = undefined;
  }

  private isRunning(): boolean {
    return Boolean(this.proc && !this.proc.killed && this.proc.stdin.writable);
  }

  private isRecoverable(error: unknown): boolean {
    const message = error instanceof Error ? error.message : String(error);
    return /not running|EPIPE|EINVAL|exited|disposed/i.test(message);
  }

  private handleLine(line: string): void {
    const next = this.pending.shift();
    if (!next) {
      return;
    }
    clearTimeout(next.timeout);
    try {
      next.resolve(JSON.parse(line));
    } catch (error) {
      next.reject(error instanceof Error ? error : new Error(String(error)));
    }
  }

  private rejectAll(error: Error): void {
    for (const entry of this.pending.splice(0)) {
      clearTimeout(entry.timeout);
      entry.reject(error);
    }
  }

  private removePending(entry: PendingRequest): void {
    clearTimeout(entry.timeout);
    const index = this.pending.indexOf(entry);
    if (index >= 0) {
      this.pending.splice(index, 1);
    }
  }
}

class StructScopeTreeProvider implements vscode.TreeDataProvider<vscode.TreeItem> {
  private readonly changeEmitter = new vscode.EventEmitter<vscode.TreeItem | undefined | null | void>();
  readonly onDidChangeTreeData = this.changeEmitter.event;

  refresh(): void {
    this.changeEmitter.fire();
  }

  getTreeItem(element: vscode.TreeItem): vscode.TreeItem {
    return element;
  }

  getChildren(): vscode.ProviderResult<vscode.TreeItem[]> {
    const items: vscode.TreeItem[] = [
      actionItem('Analyze Current File', 'structscope.analyzeStruct', 'play'),
      actionItem('Open Dashboard', 'structscope.openPanel', 'layout-panel'),
      actionItem('Run CLI in Terminal', 'structscope.runCliInTerminal', 'terminal'),
      actionItem('Copy Last JSON', 'structscope.copyAnalysisJson', 'copy'),
      actionItem('Show Output Log', 'structscope.showOutput', 'output')
    ];

    items.push(infoItem(`Platform: ${selectedPlatform}${detectedPlatformLabel ? ` (${detectedPlatformLabel})` : ''}`, 'circuit-board'));
    items.push(infoItem(`Cache line: ${selectedCacheLine}B`, 'symbol-numeric'));
    items.push(infoItem(`Last struct: ${lastStructName || 'none'}`, 'symbol-structure'));
    return items;
  }
}

function actionItem(label: string, command: string, icon: string): vscode.TreeItem {
  const item = new vscode.TreeItem(label, vscode.TreeItemCollapsibleState.None);
  item.iconPath = new vscode.ThemeIcon(icon);
  item.command = { command, title: label };
  return item;
}

function infoItem(label: string, icon: string): vscode.TreeItem {
  const item = new vscode.TreeItem(label, vscode.TreeItemCollapsibleState.None);
  item.iconPath = new vscode.ThemeIcon(icon);
  return item;
}

let outputChannel: vscode.OutputChannel | undefined;
let currentPanel: vscode.WebviewPanel | undefined;
let diagnosticCollection: vscode.DiagnosticCollection | undefined;
let statusBarItem: vscode.StatusBarItem | undefined;
let treeProvider: StructScopeTreeProvider | undefined;
let selectedPlatform = 'x86_64';
let selectedCacheLine = 64;
let detectedPlatformLabel = '';
let lastAnalysisContext: AnalysisContext | undefined;
let lastStructName: string | undefined;
let lastKnownStructs: StructAnalysis[] | undefined;
let lastAnalysisJson: string | undefined;
let selectionDebounce: NodeJS.Timeout | undefined;
let activePythonPath = 'python';

export async function activate(context: vscode.ExtensionContext) {
  outputChannel = vscode.window.createOutputChannel('StructScope');
  diagnosticCollection = vscode.languages.createDiagnosticCollection('structscope');
  treeProvider = new StructScopeTreeProvider();
  context.subscriptions.push(outputChannel);
  context.subscriptions.push(diagnosticCollection);
  context.subscriptions.push(vscode.window.registerTreeDataProvider('structscope.dashboard', treeProvider));

  const server = new PythonServer();
  const serverScript = context.asAbsolutePath(path.join('python', 'server.py'));
  const requirementsPath = context.asAbsolutePath(path.join('python', 'requirements.txt'));
  const pythonCandidates = getPythonCandidates();

  // Register commands immediately so UI interactions don't say "command not found"
  context.subscriptions.push(
    vscode.commands.registerCommand('structscope.analyzeStruct', async () => {
      await analyzeActiveDocument(context, server);
    }),
    vscode.commands.registerCommand('structscope.openPanel', async () => {
      openStructScopePanel(context, server);
      if (vscode.window.activeTextEditor && languageFromDocument(vscode.window.activeTextEditor.document)) {
        await analyzeActiveDocument(context, server);
      } else {
        await rerunLastAnalysis(context, server);
      }
    }),
    vscode.commands.registerCommand('structscope.runCliInTerminal', () => {
      runCliInTerminal(context);
    }),
    vscode.commands.registerCommand('structscope.copyAnalysisJson', async () => {
      if (!lastAnalysisJson) {
        vscode.window.showInformationMessage('No StructScope analysis has run yet.');
        return;
      }
      await vscode.env.clipboard.writeText(lastAnalysisJson);
      vscode.window.showInformationMessage('StructScope analysis JSON copied.');
    }),
    vscode.commands.registerCommand('structscope.showOutput', () => {
      outputChannel?.show(true);
    })
  );

  let started = false;
  const errors: string[] = [];
  for (const pythonPath of pythonCandidates) {
    try {
      await ensurePythonDependencies(pythonPath, requirementsPath);
      await server.start(pythonPath, serverScript);
      outputChannel.appendLine(`Started Python server with ${pythonPath}`);
      activePythonPath = pythonPath;
      started = true;
      break;
    } catch (error) {
      errors.push(`${pythonPath}: ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  if (!started) {
    const message = `StructScope could not start Python. ${errors.join(' | ')}`;
    outputChannel.appendLine(message);
    vscode.window.showErrorMessage(message);
    return;
  }

  try {
    const ping = await server.send({ method: 'ping' }, getSettings().requestTimeoutMs);
    outputChannel.appendLine(`Ping response: ${JSON.stringify(ping)}`);
  } catch (error) {
    outputChannel.appendLine(`Ping failed: ${error instanceof Error ? error.message : String(error)}`);
  }

  await applyConfiguredDefaults(server);
  statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
  statusBarItem.command = 'structscope.analyzeStruct';
  statusBarItem.tooltip = 'StructScope: analyze the active C, C++, or Rust file';
  context.subscriptions.push(statusBarItem);
  updateStatusBar();

  context.subscriptions.push(
    vscode.workspace.onDidSaveTextDocument((document) => {
      void analyzeSavedDocument(context, server, document);
    }),
    vscode.workspace.onDidChangeConfiguration(async (event) => {
      if (!event.affectsConfiguration('structscope')) {
        return;
      }
      await applyConfiguredDefaults(server);
      updateStatusBar();
      treeProvider?.refresh();
      if (lastAnalysisContext) {
        await rerunLastAnalysis(context, server);
      }
    }),
    vscode.window.onDidChangeTextEditorSelection((event) => {
      if (!currentPanel) {
        return;
      }
      if (!languageFromDocument(event.textEditor.document)) {
        return;
      }
      if (selectionDebounce) {
        clearTimeout(selectionDebounce);
      }
      selectionDebounce = setTimeout(() => {
        void handleSelectionSettled(context, server, event.textEditor);
      }, 500);
    }),
    {
      dispose: () => {
        if (selectionDebounce) {
          clearTimeout(selectionDebounce);
        }
      }
    },
    { dispose: () => server.dispose() }
  );

  const activeEditor = vscode.window.activeTextEditor;
  if (activeEditor && languageFromDocument(activeEditor.document) && getSettings().analyzeOnSave && currentPanel) {
    void analyzeActiveDocument(context, server);
  }
}

export function deactivate() {
  // VS Code disposes subscriptions registered during activation.
}

function getPythonCandidates(): string[] {
  const configured = vscode.workspace.getConfiguration('structscope').get<string>('pythonPath')?.trim();
  if (configured) {
    return [configured, 'python3', 'python'];
  }
  return ['python3', 'python'];
}

function getSettings(): StructScopeSettings {
  const config = vscode.workspace.getConfiguration('structscope');
  return {
    defaultPlatform: config.get<string>('defaultPlatform', 'auto'),
    cacheLine: config.get<number>('cacheLine', 64),
    analyzeOnSave: config.get<boolean>('analyzeOnSave', true),
    autoOpenPanel: config.get<boolean>('autoOpenPanel', true),
    showStatusBar: config.get<boolean>('showStatusBar', true),
    allowIncompleteLayouts: config.get<boolean>('allowIncompleteLayouts', false),
    requestTimeoutMs: Math.max(1000, config.get<number>('requestTimeoutMs', 15000)),
    autoInstallPythonDeps: config.get<boolean>('autoInstallPythonDeps', true)
  };
}

async function applyConfiguredDefaults(server: PythonServer): Promise<void> {
  const settings = getSettings();
  selectedCacheLine = settings.cacheLine;
  if (settings.defaultPlatform === 'auto') {
    try {
      selectedPlatform = await detectPlatform(server);
      detectedPlatformLabel = 'auto';
    } catch (error) {
      selectedPlatform = 'x86_64';
      detectedPlatformLabel = 'fallback';
      outputChannel?.appendLine(`Host ABI detection failed, falling back to x86_64: ${error instanceof Error ? error.message : String(error)}`);
    }
  } else {
    selectedPlatform = settings.defaultPlatform;
    detectedPlatformLabel = '';
  }
  outputChannel?.appendLine(`Defaults: platform=${selectedPlatform}${detectedPlatformLabel ? ' via auto-detect' : ''}, cacheLine=${selectedCacheLine}`);
}

async function detectPlatform(server: PythonServer): Promise<string> {
  const response = (await server.send({ method: 'detect_platform' }, getSettings().requestTimeoutMs)) as DetectPlatformResponse;
  if (response.error) {
    throw new Error(response.error);
  }
  const platform = response.platform || 'x86_64';
  outputChannel?.appendLine(
    `Detected host platform: ${platform} (${response.system || 'unknown'} ${response.machine || 'unknown'}, pointer=${response.pointer_size || '?'}B, abi=${response.abi || '?'})`
  );
  if (response.warning) {
    outputChannel?.appendLine(`Detection note: ${response.warning}`);
  }
  return platform;
}

async function ensurePythonDependencies(pythonPath: string, requirementsPath: string): Promise<void> {
  const check = await checkPythonDependencies(pythonPath);
  if (check.ok) {
    outputChannel?.appendLine(`Python dependency check passed for ${pythonPath}`);
    return;
  }

  const settings = getSettings();
  const installHint = `${pythonPath} -m pip install -r ${requirementsPath}`;
  if (!settings.autoInstallPythonDeps) {
    throw new Error(`Missing Python dependencies for ${pythonPath}. Run: ${installHint}. Details: ${check.output}`);
  }

  outputChannel?.appendLine(`Python dependencies missing for ${pythonPath}; running pip install.`);
  outputChannel?.appendLine(check.output);
  await execFileChecked(pythonPath, ['-m', 'pip', 'install', '-r', requirementsPath], 180000);
  const recheck = await checkPythonDependencies(pythonPath);
  if (!recheck.ok) {
    throw new Error(`Python dependency installation completed but imports still fail. Details: ${recheck.output}`);
  }
  outputChannel?.appendLine(`Python dependencies installed for ${pythonPath}`);
}

async function checkPythonDependencies(pythonPath: string): Promise<{ ok: boolean; output: string }> {
  const code = [
    'import tree_sitter',
    'import tree_sitter_c',
    'import tree_sitter_cpp',
    'import tree_sitter_rust',
    'print("ok")'
  ].join('; ');
  try {
    const output = await execFileChecked(pythonPath, ['-c', code], 30000);
    return { ok: true, output };
  } catch (error) {
    return { ok: false, output: error instanceof Error ? error.message : String(error) };
  }
}

function execFileChecked(command: string, args: string[], timeoutMs: number): Promise<string> {
  return new Promise((resolve, reject) => {
    childProcess.execFile(
      command,
      args,
      {
        timeout: timeoutMs,
        maxBuffer: 1024 * 1024
      },
      (error, stdout, stderr) => {
        const output = `${stdout || ''}${stderr || ''}`.trim();
        if (error) {
          reject(new Error(output || error.message));
          return;
        }
        resolve(output);
      }
    );
  });
}

function updateStatusBar(): void {
  if (!statusBarItem) {
    return;
  }
  if (!getSettings().showStatusBar) {
    statusBarItem.hide();
    return;
  }
  const suffix = lastStructName ? `: ${lastStructName}` : '';
  statusBarItem.text = `$(symbol-structure) StructScope${suffix}`;
  statusBarItem.show();
}

export function openStructScopePanel(context: vscode.ExtensionContext, server: PythonServer): vscode.WebviewPanel {
  if (currentPanel) {
    currentPanel.reveal(vscode.ViewColumn.Beside);
    return currentPanel;
  }

  const panel = vscode.window.createWebviewPanel(
    'structscope',
    'StructScope',
    vscode.ViewColumn.Beside,
    {
      enableScripts: true,
      localResourceRoots: [vscode.Uri.joinPath(context.extensionUri, 'webview')]
    }
  );

  panel.webview.html = getWebviewHtml(context, panel.webview);
  panel.webview.onDidReceiveMessage(async (message) => {
    outputChannel?.appendLine(`Webview message: ${JSON.stringify(message)}`);
    if (message?.type === 'platform-change' && typeof message.platform === 'string') {
      selectedPlatform = message.platform === 'auto' ? await detectPlatform(server) : message.platform;
      detectedPlatformLabel = message.platform === 'auto' ? 'auto' : '';
      updateStatusBar();
      treeProvider?.refresh();
      await rerunLastAnalysis(context, server);
    }
    if (message?.type === 'detect-platform') {
      selectedPlatform = await detectPlatform(server);
      detectedPlatformLabel = 'auto';
      updateStatusBar();
      treeProvider?.refresh();
      await rerunLastAnalysis(context, server);
    }
    if (message?.type === 'cache-line-change') {
      const cacheLine = Number(message.cacheLine);
      if (Number.isFinite(cacheLine) && cacheLine > 0) {
        selectedCacheLine = cacheLine;
        updateStatusBar();
        treeProvider?.refresh();
        await rerunLastAnalysis(context, server);
      }
    }
    if (message?.type === 'analyze-active') {
      await analyzeActiveDocument(context, server);
    }
  });
  panel.onDidDispose(() => {
    currentPanel = undefined;
  });

  currentPanel = panel;
  return panel;
}

function getWebviewHtml(context: vscode.ExtensionContext, webview: vscode.Webview): string {
  const htmlPath = vscode.Uri.joinPath(context.extensionUri, 'webview', 'index.html');
  const styleUri = webview.asWebviewUri(vscode.Uri.joinPath(context.extensionUri, 'webview', 'styles.css'));
  const scriptUri = webview.asWebviewUri(vscode.Uri.joinPath(context.extensionUri, 'webview', 'byteMap.js'));
  const nonce = getNonce();

  return fs
    .readFileSync(htmlPath.fsPath, 'utf8')
    .replace(/\{\{cspSource\}\}/g, webview.cspSource)
    .replace(/\{\{styleUri\}\}/g, styleUri.toString())
    .replace(/\{\{scriptUri\}\}/g, scriptUri.toString())
    .replace(/\{\{nonce\}\}/g, nonce);
}

function getNonce(): string {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  let value = '';
  for (let i = 0; i < 32; i += 1) {
    value += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return value;
}

function languageFromDocument(document: vscode.TextDocument): SupportedLanguage | undefined {
  if (document.languageId === 'c') {
    return 'c';
  }
  if (document.languageId === 'cpp') {
    return 'cpp';
  }
  if (document.languageId === 'rust') {
    return 'rust';
  }
  const ext = path.extname(document.fileName).toLowerCase();
  if (ext === '.c' || ext === '.h') {
    return 'c';
  }
  if (ext === '.cc' || ext === '.cpp' || ext === '.cxx' || ext === '.hpp' || ext === '.hh' || ext === '.hxx') {
    return 'cpp';
  }
  if (ext === '.rs') {
    return 'rust';
  }
  return undefined;
}

async function analyzeActiveDocument(context: vscode.ExtensionContext, server: PythonServer): Promise<void> {
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    vscode.window.showErrorMessage('No active editor to analyse.');
    return;
  }

  const language = languageFromDocument(editor.document);
  if (!language) {
    vscode.window.showInformationMessage('StructScope supports C, C++, and Rust.');
    return;
  }

  const analysisContext: AnalysisContext = {
    uri: editor.document.uri,
    source: editor.document.getText(),
    language,
    cursorLine: editor.selection.active.line + 1
  };
  await runAnalysis(context, server, analysisContext, true);
}

async function analyzeSavedDocument(
  context: vscode.ExtensionContext,
  server: PythonServer,
  document: vscode.TextDocument
): Promise<void> {
  const settings = getSettings();
  if (!settings.analyzeOnSave) {
    return;
  }
  const language = languageFromDocument(document);
  if (!language) {
    return;
  }
  const editor = vscode.window.visibleTextEditors.find((item) => item.document.uri.toString() === document.uri.toString());
  const cursorLine = editor ? editor.selection.active.line + 1 : 1;
  await runAnalysis(
    context,
    server,
    {
      uri: document.uri,
      source: document.getText(),
      language,
      cursorLine
    },
    settings.autoOpenPanel
  );
}

function runCliInTerminal(context: vscode.ExtensionContext): void {
  const editor = vscode.window.activeTextEditor;
  if (!editor) {
    vscode.window.showErrorMessage('No active editor to analyze with StructScope CLI.');
    return;
  }
  const language = languageFromDocument(editor.document);
  if (!language) {
    vscode.window.showInformationMessage('StructScope supports C, C++, and Rust.');
    return;
  }
  if (editor.document.isUntitled || editor.document.uri.scheme !== 'file') {
    vscode.window.showErrorMessage('Save the file before running StructScope CLI in a terminal.');
    return;
  }

  const cliScript = context.asAbsolutePath(path.join('python', 'cli.py'));
  const args = [
    quoteShell(activePythonPath),
    quoteShell(cliScript),
    quoteShell(editor.document.uri.fsPath),
    '--language',
    language,
    '--platform',
    selectedPlatform,
    '--cache-line',
    String(selectedCacheLine)
  ];
  if (getSettings().allowIncompleteLayouts) {
    args.push('--allow-incomplete');
  }

  const terminal = vscode.window.createTerminal({ name: 'StructScope CLI' });
  terminal.sendText(args.join(' '));
  terminal.show();
}

function quoteShell(value: string): string {
  if (process.platform === 'win32') {
    return `"${value.replace(/"/g, '\\"')}"`;
  }
  return `'${value.replace(/'/g, "'\\''")}'`;
}

async function rerunLastAnalysis(context: vscode.ExtensionContext, server: PythonServer): Promise<void> {
  const editor = vscode.window.activeTextEditor;
  if (editor) {
    const language = languageFromDocument(editor.document);
    if (language) {
      lastAnalysisContext = {
        uri: editor.document.uri,
        source: editor.document.getText(),
        language,
        cursorLine: editor.selection.active.line + 1
      };
    }
  }
  if (!lastAnalysisContext) {
    return;
  }
  await runAnalysis(context, server, lastAnalysisContext, false);
}

async function runAnalysis(
  context: vscode.ExtensionContext,
  server: PythonServer,
  analysisContext: AnalysisContext,
  revealPanel: boolean
): Promise<void> {
  const request = {
    method: 'analyse',
    source: analysisContext.source,
    language: analysisContext.language,
    platform: selectedPlatform,
    cache_line: selectedCacheLine,
    allow_incomplete: getSettings().allowIncompleteLayouts
  };

  let response: AnalyseResponse;
  try {
    response = (await server.send(request, getSettings().requestTimeoutMs)) as AnalyseResponse;
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    outputChannel?.appendLine(`Analysis request failed: ${message}`);
    vscode.window.showErrorMessage(`StructScope analysis failed: ${message}`);
    return;
  }

  outputChannel?.appendLine(`Analysis response: ${JSON.stringify(response)}`);
  if (response.error) {
    outputChannel?.appendLine(`Python error: ${response.error}`);
    vscode.window.showErrorMessage(`StructScope analysis failed: ${response.error}`);
    return;
  }
  selectedPlatform = response.platform || selectedPlatform;
  selectedCacheLine = response.cache_line || selectedCacheLine;
  if (!response.structs || response.structs.length === 0) {
    clearDiagnostics(analysisContext.uri);
    lastKnownStructs = undefined;
    vscode.window.showInformationMessage('No structs found in the active document.');
    return;
  }
  lastKnownStructs = response.structs;
  lastAnalysisJson = JSON.stringify(response, null, 2);

  const document = vscode.workspace.textDocuments.find((candidate) => candidate.uri.toString() === analysisContext.uri.toString());
  if (document) {
    updateDiagnostics(document, response.structs);
  }

  const selected = findNearestStruct(response.structs, analysisContext.cursorLine);
  if (!selected) {
    vscode.window.showInformationMessage('No structs found near the cursor.');
    return;
  }

  lastAnalysisContext = analysisContext;
  lastStructName = selected.name;
  updateStatusBar();
  treeProvider?.refresh();
  const panel = revealPanel || currentPanel ? openStructScopePanel(context, server) : undefined;
  if (panel && revealPanel) {
    panel.reveal(vscode.ViewColumn.Beside);
  }

  if (panel) {
    await panel.webview.postMessage({
      type: 'layout',
      data: {
        ...selected,
        platform: selectedPlatform,
        platform_source: detectedPlatformLabel || 'manual',
        cache_line: selectedCacheLine
      }
    });
    await panel.webview.postMessage({
      type: 'platform',
      value: selectedPlatform,
      source: detectedPlatformLabel || 'manual',
      cacheLine: selectedCacheLine
    });
  }
}

async function handleSelectionSettled(
  context: vscode.ExtensionContext,
  server: PythonServer,
  editor: vscode.TextEditor
): Promise<void> {
  if (!currentPanel) {
    return;
  }
  const language = languageFromDocument(editor.document);
  if (!language) {
    return;
  }
  const cursorLine = editor.selection.active.line + 1;
  const nearest = lastKnownStructs && lastAnalysisContext?.uri.toString() === editor.document.uri.toString()
    ? findNearestStruct(lastKnownStructs, cursorLine)
    : undefined;

  if (nearest && nearest.name === lastStructName) {
    return;
  }

  await runAnalysis(
    context,
    server,
    {
      uri: editor.document.uri,
      source: editor.document.getText(),
      language,
      cursorLine
    },
    false
  );
}

function findNearestStruct(structs: StructAnalysis[], cursorLine: number): StructAnalysis | undefined {
  return structs.reduce<StructAnalysis | undefined>((best, candidate) => {
    if (!best) {
      return candidate;
    }
    const bestDistance = Math.abs((best.line ?? 1) - cursorLine);
    const candidateDistance = Math.abs((candidate.line ?? 1) - cursorLine);
    return candidateDistance < bestDistance ? candidate : best;
  }, undefined);
}

function updateDiagnostics(document: vscode.TextDocument, structs: StructAnalysis[]): void {
  const diagnostics: vscode.Diagnostic[] = [];

  for (const struct of structs) {
    const fields = struct.layout?.fields || [];
    for (const field of fields) {
      const fieldLine = field.line ?? struct.line;
      if (Number(field.padding_after || 0) > 0) {
        diagnostics.push(
          new vscode.Diagnostic(
            rangeForLine(document, fieldLine),
            `${field.padding_after} bytes of padding after this field`,
            vscode.DiagnosticSeverity.Hint
          )
        );
      }
    }

    for (const split of struct.analysis?.cache_line_splits || []) {
      const field = fields.find((candidate) => candidate.name === split.field_name);
      diagnostics.push(
        new vscode.Diagnostic(
          rangeForLine(document, field?.line ?? struct.line),
          'This field straddles a cache line boundary',
          vscode.DiagnosticSeverity.Warning
        )
      );
    }

    for (const blocker of struct.analysis?.blockers || []) {
      diagnostics.push(
        new vscode.Diagnostic(
          rangeForLine(document, blocker.line ?? struct.line),
          `StructScope exact layout unavailable: ${blocker.message}`,
          vscode.DiagnosticSeverity.Warning
        )
      );
    }

    if (Number(struct.analysis?.waste_ratio || 0) > 0.2) {
      diagnostics.push(
        new vscode.Diagnostic(
          rangeForLine(document, struct.line),
          `Struct is ${Math.round(struct.analysis.waste_ratio * 100)}% padding - consider reordering fields`,
          vscode.DiagnosticSeverity.Hint
        )
      );
    }
  }

  diagnosticCollection?.set(document.uri, diagnostics);
}

function clearDiagnostics(uri: vscode.Uri): void {
  diagnosticCollection?.set(uri, []);
}

function rangeForLine(document: vscode.TextDocument, oneBasedLine: number | undefined): vscode.Range {
  const line = Math.min(Math.max((oneBasedLine ?? 1) - 1, 0), Math.max(document.lineCount - 1, 0));
  const textLine = document.lineAt(line);
  return new vscode.Range(line, 0, line, textLine.range.end.character);
}
