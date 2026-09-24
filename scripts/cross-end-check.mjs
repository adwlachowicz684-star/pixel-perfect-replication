#!/usr/bin/env node
/**
 * 跨端一致性检查（C1-C4）
 *
 *   C1 命令存在性   —— 定义了没注册 / 注册了没定义 / 前端调用了不存在的命令
 *   C2 参数名一致性 —— 前端传的参数名 ≠ Rust 参数名
 *   C3 必填可选匹配 —— Rust 非 Option 的参数，前端没传
 *   C4 DTO 字段一致性 —— Rust struct 字段 ≠ TS interface 字段
 *
 * 用法:
 *   node cross-end-check.mjs                 # 用下方 CONFIG
 *   node cross-end-check.mjs --strict        # 有错退出码 1（CI 用）
 *   node cross-end-check.mjs --config x.json # 外部配置
 *
 * ⚠️ 写完必须做故障注入验证（F1-F4），永远绿灯的脚本等于没有。
 */

import fs from 'node:fs';
import path from 'node:path';

// ─────────────────────────── 配置（换项目改这里） ───────────────────────────
const CONFIG = {
  // Rust 命令所在目录（会递归读取 .rs）
  rustCmdDirs: ['src-tauri/src/fpx'],
  // 注册文件
  registerFile: 'src-tauri/src/main.rs',
  registerPattern: /fpx::(fpx_\w+)/g,
  // 前端调用文件
  apiFile: 'plugins/project-group/api.ts',
  apiCallPattern: /call<[^>]*>\(\s*'([\w:]+)'\s*,\s*\{([^}]*)\}/g,
  // 前端类型文件
  typesFile: 'plugins/project-group/types.ts',
  // Rust DTO 文件列表（不存在则跳过）
  dtoFiles: [
    'src-tauri/src/fpx/model.rs',
    'src-tauri/src/fpx/backup.rs',
    'src-tauri/src/fpx/screen.rs',
    'src-tauri/src/fpx/chain.rs',
    'src-tauri/src/fpx/watch.rs',
    'src-tauri/src/fpx/editor.rs',
  ],
  // Tauri 注入参数，不是前端传的
  injectedParams: new Set(['app', 'state', 'window', 'handle', 'app_handle']),
  // 结构体改名映射（不是错误）
  structAlias: { ChainActionItem: 'ChainAction' },
  // 只内部使用、不暴露前端
  internalOnly: new Set(['LinkRecord']),
};

const args = process.argv.slice(2);
const strict = args.includes('--strict');
const cfgIdx = args.indexOf('--config');
if (cfgIdx >= 0 && args[cfgIdx + 1]) {
  Object.assign(CONFIG, JSON.parse(fs.readFileSync(args[cfgIdx + 1], 'utf8')));
  CONFIG.injectedParams = new Set(CONFIG.injectedParams || []);
  CONFIG.internalOnly = new Set(CONFIG.internalOnly || []);
}

const errors = [];
const warns = [];
const err = (tag, msg) => errors.push(`[${tag}] ${msg}`);
const warn = (msg) => warns.push(msg);

// ─────────────────────────── 工具 ───────────────────────────
function readIfExists(p) {
  try {
    return fs.readFileSync(p, 'utf8');
  } catch {
    return null;
  }
}

function walkRs(dir) {
  const out = [];
  if (!fs.existsSync(dir)) return out;
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) out.push(...walkRs(full));
    else if (e.name.endsWith('.rs')) out.push(full);
  }
  return out;
}

/** 按括号配对截取，避免 [^}]* 提前截断 */
function readBraced(src, openIdx) {
  let depth = 0;
  for (let j = openIdx; j < src.length; j++) {
    if (src[j] === '{') depth++;
    else if (src[j] === '}') {
      depth--;
      if (depth === 0) return src.slice(openIdx + 1, j);
    }
  }
  return src.slice(openIdx + 1);
}

function readParen(src, openIdx) {
  let depth = 0;
  for (let j = openIdx; j < src.length; j++) {
    if (src[j] === '(') depth++;
    else if (src[j] === ')') {
      depth--;
      if (depth === 0) return src.slice(openIdx + 1, j);
    }
  }
  return src.slice(openIdx + 1);
}

const snakeToCamel = (s) => s.replace(/_([a-z])/g, (_, c) => c.toUpperCase());

// ─────────────────────────── 抽取 ───────────────────────────
/** Rust 命令定义：#[tauri::command] 下的 pub (async)? fn */
function parseRustCommands() {
  const map = new Map();
  for (const dir of CONFIG.rustCmdDirs) {
    for (const file of walkRs(dir)) {
      const src = readIfExists(file);
      if (src == null) continue;
      const attrRe = /#\[tauri::command([^\]]*)\]\s*(?:pub\s+)?(async\s+)?fn\s+(\w+)\s*\(/g;
      let m;
      while ((m = attrRe.exec(src))) {
        const attr = m[1] || '';
        const renameAll = /rename_all\s*=\s*"(\w+)"/.exec(attr)?.[1] || null;
        const name = m[3];
        const body = readParen(src, attrRe.lastIndex - 1);
        const params = body
          .split(',')
          .map((s) => s.trim())
          .filter(Boolean)
          .map((s) => {
            const pm = /^(\w+)\s*:\s*(.+)$/s.exec(s);
            return pm ? { name: pm[1], type: pm[2].trim() } : null;
          })
          .filter(Boolean)
          .filter((p) => !CONFIG.injectedParams.has(p.name));
        map.set(name, {
          file,
          params,
          optional: new Set(params.filter((p) => /^Option\s*</.test(p.type)).map((p) => p.name)),
          renameAll,
        });
      }
    }
  }
  return map;
}

function parseRegistered() {
  const src = readIfExists(CONFIG.registerFile);
  if (src == null) return new Set();
  return new Set([...src.matchAll(CONFIG.registerPattern)].map((m) => m[1]));
}

/** 前端调用：call<T>('cmd', { ... }) */
function parseApiCalls() {
  const src = readIfExists(CONFIG.apiFile);
  const map = new Map();
  if (src == null) return map;
  const re = new RegExp(CONFIG.apiCallPattern.source, 'g');
  let m;
  while ((m = re.exec(src))) {
    const name = m[1];
    const keys = (m[2] || '')
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
      .map((k) => {
        const km = /^(\w+)\s*:/.exec(k);
        // 简写属性 { kind } 没有冒号
        return km ? km[1] : k.replace(/[^\w]/g, '');
      })
      .filter(Boolean);
    map.set(name, new Set(keys));
  }
  return map;
}

function parseRustStructs() {
  const map = new Map();
  for (const f of CONFIG.dtoFiles) {
    const src = readIfExists(f);
    if (src == null) continue;
    const re = /pub\s+struct\s+(\w+)\s*\{/g;
    let m;
    while ((m = re.exec(src))) {
      const body = readBraced(src, re.lastIndex - 1);
      const fields = [...body.matchAll(/(?:pub\s+)?(\w+)\s*:/g)].map((x) => x[1]);
      map.set(m[1], fields);
    }
  }
  return map;
}

function parseTsInterfaces() {
  const src = readIfExists(CONFIG.typesFile);
  const map = new Map();
  if (src == null) return map;
  const re = /(?:export\s+)?interface\s+(\w+)\s*\{/g;
  let m;
  while ((m = re.exec(src))) {
    const body = readBraced(src, re.lastIndex - 1);
    const fields = [...body.matchAll(/^\s*(\w+)\??\s*:/gm)].map((x) => x[1]);
    map.set(m[1], fields);
  }
  return map;
}

// ─────────────────────────── 检查 ───────────────────────────
const defined = parseRustCommands();
const registered = parseRegistered();
const called = parseApiCalls();
const rustStructs = parseRustStructs();
const tsIfaces = parseTsInterfaces();

console.log('='.repeat(60));
console.log(`Rust 命令 ${defined.size} · 注册 ${registered.size} · 前端调用 ${called.size}`);
console.log(`Rust DTO ${rustStructs.size} · TS interface ${tsIfaces.size}`);
console.log('='.repeat(60));

// C1 命令存在性
for (const [name, info] of defined) {
  if (!registered.has(name)) err('注册缺失', `${name}（${info.file}）—— 前端调用必失败`);
}
for (const name of registered) {
  if (!defined.has(name)) err('定义缺失', `${name} —— 注册了但没有定义`);
}
for (const name of called.keys()) {
  if (!defined.has(name)) err('孤儿调用', `${name} —— 前端调了个不存在的命令`);
}

// C2 参数名一致性 + C3 必填可选
for (const [name, sentKeys] of called) {
  const def = defined.get(name);
  if (!def) continue;
  const expect = def.params.map((p) => {
    if (def.renameAll === 'snake_case') return p.name;
    if (def.renameAll === 'camelCase') return snakeToCamel(p.name);
    return p.name;
  });
  for (const k of sentKeys) {
    if (!expect.includes(k)) {
      err('参数名不符', `${name}: 前端传了 \`${k}\`，Rust 侧无此参数（会静默变 undefined）`);
    }
  }
  for (const p of def.params) {
    const want = def.renameAll === 'camelCase' ? snakeToCamel(p.name) : p.name;
    if (!def.optional.has(p.name) && !sentKeys.has(want)) {
      err('必传参数缺失', `${name}: Rust 非 Option 参数 \`${p.name}\` 前端没传`);
    }
  }
}

// C4 DTO 字段一致性
for (const [rName, rFields] of rustStructs) {
  if (CONFIG.internalOnly.has(rName)) {
    warn(`${rName} 为内部结构体，不暴露前端（提示，非错误）`);
    continue;
  }
  const tName = CONFIG.structAlias[rName] || rName;
  const tFields = tsIfaces.get(tName);
  if (!tFields) {
    if (!CONFIG.structAlias[rName]) warn(`${rName} 在 TS 侧无对应 interface（可能只在 Rust 内部用）`);
    else err('DTO 缺失', `${rName}(→${tName}) 在 TS 侧找不到`);
    continue;
  }
  const rc = new Set(rFields.map(snakeToCamel));
  const tc = new Set(tFields);
  for (const f of rc) {
    if (!tc.has(f)) {
      err('DTO 字段缺失', `${tName}.${f} —— 前端读到 undefined，或保存时被静默丢弃`);
    }
  }
  for (const f of tc) {
    if (!rc.has(f)) {
      err('DTO 字段多余', `${tName}.${f} —— Rust 不认识，整份回传时被丢弃`);
    }
  }
}

// ─────────────────────────── 输出 ───────────────────────────
for (const w of warns) console.log(`⚠️  ${w}`);
if (errors.length) {
  console.log('');
  for (const e of errors) console.log(`❌ ${e}`);
  console.log(`\n共 ${errors.length} 处不一致`);
  process.exit(strict ? 1 : 0);
} else {
  console.log('✅ 全部一致');
  if (!warns.length) console.log('（无任何提示）');
  console.log('\n⚠️ 若这是本脚本第一次全绿，请先做故障注入验证（F1-F4）再信它。');
  process.exit(0);
}
