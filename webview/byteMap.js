const vscode = acquireVsCodeApi();

const FIELD_COLORS = [
  'hsl(207 82% 62%)',
  'hsl(28 90% 58%)',
  'hsl(145 58% 48%)',
  'hsl(342 78% 64%)',
  'hsl(49 88% 56%)',
  'hsl(188 72% 48%)',
  'hsl(265 72% 70%)',
  'hsl(12 78% 62%)'
];

const state = {
  lastStruct: null,
  fieldColors: new Map(),
  platform: 'x86_64',
  platformSource: 'manual',
  cacheLine: 64,
  lastJson: ''
};

window.structscope = {
  vscode,
  buildCells
};

const els = {
  platform: document.getElementById('platform'),
  analyzeActive: document.getElementById('analyze-active'),
  detectPlatform: document.getElementById('detect-platform'),
  copyJson: document.getElementById('copy-json'),
  copyReport: document.getElementById('copy-report'),
  cacheLine: document.getElementById('cache-line'),
  byteMap: document.getElementById('byte-map'),
  fieldTable: document.getElementById('field-table'),
  insights: document.getElementById('insights'),
  suggestions: document.getElementById('suggestions'),
  metrics: document.getElementById('metrics')
};

window.addEventListener('message', (event) => {
  const message = event.data;
  if (!message || typeof message !== 'object') {
    return;
  }
  if (message.type === 'layout') {
    console.log('Received layout:', message.data);
    state.lastStruct = message.data;
    state.lastJson = JSON.stringify(message.data, null, 2);
    state.platform = message.data.platform || state.platform;
    state.platformSource = message.data.platform_source || state.platformSource || 'manual';
    state.cacheLine = Number(message.data.cache_line || state.cacheLine || 64);
    renderStruct(message.data);
  }
  if (message.type === 'platform' && typeof message.value === 'string') {
    state.platform = message.value;
    state.platformSource = message.source || state.platformSource || 'manual';
    state.cacheLine = Number(message.cacheLine || state.cacheLine || 64);
    if (els.platform) {
      els.platform.value = message.value;
    }
    if (els.cacheLine) {
      els.cacheLine.value = String(state.cacheLine);
    }
    if (state.lastStruct) {
      renderMetrics(state.lastStruct.layout, state.lastStruct.analysis, els.metrics);
    }
  }
});

if (els.platform) {
  els.platform.addEventListener('change', () => {
    vscode.postMessage({ type: 'platform-change', platform: els.platform.value });
  });
}

if (els.analyzeActive) {
  els.analyzeActive.addEventListener('click', () => {
    vscode.postMessage({ type: 'analyze-active' });
  });
}

if (els.detectPlatform) {
  els.detectPlatform.addEventListener('click', () => {
    vscode.postMessage({ type: 'detect-platform' });
  });
}

if (els.cacheLine) {
  els.cacheLine.addEventListener('change', () => {
    state.cacheLine = Number(els.cacheLine.value || 64);
    vscode.postMessage({ type: 'cache-line-change', cacheLine: state.cacheLine });
  });
}

if (els.copyJson) {
  els.copyJson.addEventListener('click', async () => {
    if (state.lastJson) {
      await navigator.clipboard.writeText(state.lastJson);
    }
  });
}

if (els.copyReport) {
  els.copyReport.addEventListener('click', async () => {
    if (state.lastStruct) {
      await navigator.clipboard.writeText(buildMarkdownReport(state.lastStruct));
    }
  });
}

function renderStruct(structData) {
  const layout = structData.layout;
  const analysis = structData.analysis;
  const cells = buildCells(structData);
  console.log('Built byte cells:', cells.length, 'expected:', layout.total_size);

  renderMetrics(layout, analysis, els.metrics);
  renderByteMapWithRuler(cells, layout, analysis, els.byteMap, state.cacheLine);
  renderFieldTable(layout, analysis, els.fieldTable);
  renderInsights(structData, els.insights);
  renderSuggestions(structData.name, layout, analysis, els.suggestions);
}

function buildCells(structData) {
  const layout = structData.layout;
  const fields = layout.fields || [];
  state.fieldColors = new Map();
  fields.forEach((field, index) => {
    state.fieldColors.set(field.name, FIELD_COLORS[index % FIELD_COLORS.length]);
  });

  const cells = Array.from({ length: layout.total_size }, (_, index) => ({
    index,
    type: 'trailing'
  }));

  fields.forEach((field, fieldIndex) => {
    const offset = Number(field.offset || 0);
    const size = Number(field.size || 0);
    for (let byte = 0; byte < size && offset + byte < cells.length; byte += 1) {
      cells[offset + byte] = {
        index: offset + byte,
        type: 'field',
        fieldName: field.name,
        fieldIndex,
        byteInField: byte,
        fieldType: field.raw_type || field.type || '',
        fieldOffset: offset,
        fieldSize: size,
        color: state.fieldColors.get(field.name)
      };
    }

    const paddingStart = offset + size;
    const paddingEnd = paddingStart + Number(field.padding_after || 0);
    for (let index = paddingStart; index < paddingEnd && index < cells.length; index += 1) {
      cells[index] = {
        index,
        type: 'padding',
        fieldName: field.name,
        fieldIndex,
        byteInField: index - paddingStart
      };
    }
  });

  return cells;
}

function renderByteMapWithRuler(cells, layoutResult, analysisResult, containerEl, cacheLineSize) {
  if (!containerEl) {
    return;
  }
  containerEl.replaceChildren();
  renderCacheLineRuler(layoutResult.total_size, cacheLineSize, containerEl);
  const grid = document.createElement('div');
  grid.className = 'byte-grid';
  containerEl.appendChild(grid);
  renderByteMap(cells, grid, analysisResult);
}

function renderByteMap(cells, containerEl, analysisResult) {
  containerEl.replaceChildren();
  const splitIndexes = splitByteIndexes(analysisResult);

  cells.forEach((cell, index) => {
    const cellEl = document.createElement('div');
    cellEl.className = `byte-cell ${cell.type}`;
    if (splitIndexes.has(cell.index)) {
      cellEl.classList.add('split');
    }
    if (cell.type === 'field') {
      cellEl.style.backgroundColor = cell.color;
      cellEl.title = `${cell.fieldName} | type ${cell.fieldType} | offset ${cell.fieldOffset} | byte ${cell.byteInField}`;
      const label = document.createElement('span');
      label.textContent = String(cell.byteInField);
      cellEl.appendChild(label);
    } else if (cell.type === 'padding') {
      cellEl.title = `padding byte ${cell.index} after ${cell.fieldName}`;
    } else {
      cellEl.title = `trailing padding byte ${cell.index}`;
    }

    const next = cells[index + 1];
    const sameGroup = next && cell.type === 'field' && next.type === 'field' && next.fieldName === cell.fieldName;
    cellEl.style.marginRight = sameGroup ? '0' : '1px';
    containerEl.appendChild(cellEl);
  });
}

function renderCacheLineRuler(totalSize, cacheLineSize, containerEl) {
  const ruler = document.createElement('div');
  ruler.className = 'cache-ruler';
  const lineSize = Number(cacheLineSize || 64);
  const total = Number(totalSize || 0);
  if (total > lineSize) {
    for (let boundary = lineSize; boundary < total; boundary += lineSize) {
      const marker = document.createElement('div');
      marker.className = 'cache-marker';
      marker.style.left = `${boundary * 21}px`;
      const label = document.createElement('span');
      label.textContent = `${boundary}B`;
      marker.appendChild(label);
      ruler.appendChild(marker);
    }
  }
  containerEl.appendChild(ruler);
}

function renderFieldTable(layoutResult, analysisResult, tableEl) {
  if (!tableEl) {
    return;
  }
  tableEl.replaceChildren();

  const table = document.createElement('table');
  table.className = 'field-table';
  const caption = document.createElement('caption');
  caption.textContent = 'Struct field layout';
  table.appendChild(caption);
  const thead = table.createTHead();
  const header = thead.insertRow();
  ['Field', 'Type', 'Offset', 'Size', 'Pad after', 'Note'].forEach((label) => {
    const th = document.createElement('th');
    th.textContent = label;
    header.appendChild(th);
  });

  const splitNames = new Set((analysisResult.cache_line_splits || []).map((split) => split.field_name));
  const tbody = table.createTBody();
  (layoutResult.fields || []).forEach((field) => {
    const row = tbody.insertRow();
    const nameCell = row.insertCell();
    const swatch = document.createElement('span');
    swatch.className = 'field-swatch';
    swatch.style.backgroundColor = state.fieldColors.get(field.name) || FIELD_COLORS[0];
    nameCell.appendChild(swatch);
    nameCell.appendChild(document.createTextNode(field.name));
    row.insertCell().textContent = field.raw_type || field.type || '';
    row.insertCell().textContent = String(field.offset);
    row.insertCell().textContent = String(field.size);
    row.insertCell().textContent = String(field.padding_after || 0);

    const notes = [];
    if (splitNames.has(field.name)) {
      notes.push('cache split');
    }
    if (Number(field.padding_after || 0) > 0) {
      notes.push('padding');
    }
    row.insertCell().textContent = notes.join(', ');
  });

  tableEl.appendChild(table);

  const summary = document.createElement('div');
  summary.className = 'table-summary';
  const percent = percentage(analysisResult.waste_ratio);
  summary.textContent = `Total: ${layoutResult.total_size} bytes | Padding: ${analysisResult.waste_bytes} bytes (${percent}) | Optimal: ${analysisResult.optimal_size} bytes`;
  tableEl.appendChild(summary);
}

function renderSuggestions(structName, layoutResult, analysisResult, suggestEl) {
  if (!suggestEl) {
    return;
  }
  suggestEl.replaceChildren();

  if (Number(analysisResult.savings || 0) > 0) {
    const banner = document.createElement('div');
    banner.className = 'suggestion-banner';
    banner.textContent = `Reordering fields saves ${analysisResult.savings} bytes (current: ${layoutResult.total_size} -> optimal: ${analysisResult.optimal_size})`;
    suggestEl.appendChild(banner);

    const snippet = buildSuggestionSnippet(structName, analysisResult.optimal_order || layoutResult.fields || []);
    const pre = document.createElement('pre');
    const code = document.createElement('code');
    code.textContent = snippet;
    pre.appendChild(code);
    suggestEl.appendChild(pre);

    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = 'Copy suggestion';
    button.addEventListener('click', async () => {
      await navigator.clipboard.writeText(snippet);
    });
    suggestEl.appendChild(button);
  } else {
    const done = document.createElement('div');
    done.className = 'suggestion-ok';
    done.textContent = 'Field order is already optimal for this platform.';
    suggestEl.appendChild(done);
  }
}

function renderInsights(structData, insightsEl) {
  if (!insightsEl) {
    return;
  }
  insightsEl.replaceChildren();
  const analysis = structData.analysis || {};
  const header = document.createElement('div');
  header.className = 'insights-header';
  header.textContent = `Layout grade ${analysis.layout_grade || 'N/A'} - score ${analysis.layout_score ?? 'N/A'}/100`;
  insightsEl.appendChild(header);

  if (analysis.layout_complete === false || (analysis.blockers || []).length) {
    const incomplete = document.createElement('div');
    incomplete.className = 'incomplete-banner';
    incomplete.textContent = 'Layout is incomplete. Unresolved types or compiler-specific bit-fields prevent authoritative offsets.';
    insightsEl.appendChild(incomplete);
  }

  const rules = analysis.rules || [];
  if (!rules.length) {
    const empty = document.createElement('div');
    empty.className = 'insight-card';
    empty.textContent = 'No rule-based issues detected for this layout.';
    insightsEl.appendChild(empty);
    return;
  }

  rules.forEach((rule) => {
    const card = document.createElement('article');
    card.className = `insight-card severity-${rule.severity}`;

    const title = document.createElement('h2');
    title.textContent = `${rule.title} (${rule.severity})`;
    card.appendChild(title);

    const message = document.createElement('p');
    message.textContent = rule.message;
    card.appendChild(message);

    const recommendation = document.createElement('p');
    recommendation.className = 'insight-recommendation';
    recommendation.textContent = rule.recommendation;
    card.appendChild(recommendation);

    const meta = document.createElement('div');
    meta.className = 'insight-meta';
    meta.textContent = `${rule.id} | ${rule.category} | confidence: ${rule.confidence} | auto-apply: no`;
    card.appendChild(meta);
    insightsEl.appendChild(card);
  });
}

function renderMetrics(layoutResult, analysisResult, metricsEl) {
  if (!metricsEl) {
    return;
  }
  metricsEl.replaceChildren();
  metricsEl.className = 'metrics-block';

  const meta = document.createElement('div');
  meta.className = 'metrics-meta';
  meta.textContent = `Platform: ${state.platform} (${state.platformSource || 'manual'}) | Cache line: ${state.cacheLine}B`;
  metricsEl.appendChild(meta);

  const grid = document.createElement('div');
  grid.className = 'metrics-grid';
  metricsEl.appendChild(grid);

  [
    ['Total size', `${layoutResult.total_size} bytes`],
    ['Wasted', `${analysisResult.waste_bytes} bytes (${percentage(analysisResult.waste_ratio)})`],
    ['Optimal size', `${analysisResult.optimal_size} bytes`],
    ['Fields', String((layoutResult.fields || []).length)]
  ].forEach(([label, value]) => {
    const card = document.createElement('div');
    card.className = 'metric-card';
    const labelEl = document.createElement('span');
    labelEl.className = 'metric-label';
    labelEl.textContent = label;
    const valueEl = document.createElement('strong');
    valueEl.textContent = value;
    card.append(labelEl, valueEl);
    grid.appendChild(card);
  });
}

function splitByteIndexes(analysisResult) {
  const indexes = new Set();
  (analysisResult.cache_line_splits || []).forEach((split) => {
    for (let index = split.offset; index < split.offset + split.size; index += 1) {
      indexes.add(index);
    }
  });
  return indexes;
}

function buildSuggestionSnippet(structName, fields) {
  const lines = [`struct ${structName || 'Suggested'} {`];
  fields.forEach((field) => {
    lines.push(`    ${formatFieldDeclaration(field)}`);
  });
  lines.push('};');
  return lines.join('\n');
}

function formatFieldDeclaration(field) {
  const rawType = field.raw_type || field.type || 'unknown';
  return `${rawType} ${field.name};`;
}

function percentage(value) {
  return `${(Number(value || 0) * 100).toFixed(1)}%`;
}

function buildMarkdownReport(structData) {
  const layout = structData.layout;
  const analysis = structData.analysis;
  const lines = [
    `# StructScope Report: ${structData.name}`,
    '',
    `- Platform: \`${state.platform}\``,
    `- Cache line: \`${state.cacheLine}B\``,
    `- Total size: \`${layout.total_size} bytes\``,
    `- Padding: \`${analysis.waste_bytes} bytes (${percentage(analysis.waste_ratio)})\``,
    `- Grade: \`${analysis.layout_grade || 'N/A'} (${analysis.layout_score ?? 'N/A'}/100)\``,
    '',
    '| Field | Type | Offset | Size | Padding after |',
    '| --- | --- | ---: | ---: | ---: |'
  ];
  (layout.fields || []).forEach((field) => {
    lines.push(`| ${field.name} | ${field.raw_type || field.type || ''} | ${field.offset} | ${field.size} | ${field.padding_after || 0} |`);
  });
  if ((analysis.rules || []).length) {
    lines.push('', '## Rule-based guidance', '');
    analysis.rules.forEach((rule) => {
      lines.push(`- **${rule.title}** (${rule.severity}): ${rule.recommendation}`);
    });
  }
  return lines.join('\n');
}
