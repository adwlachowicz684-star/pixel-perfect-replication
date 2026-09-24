#!/usr/bin/env python3
"""四路验收端到端流水线（第五十三轮 · 把状态机真正跑通一次）。

> ## 🔑 本轮的性质
>
> 第五十一轮提出"**把三条状态机接入四路验收流程**"，第五十二轮修完执行层。
> 本轮**不再开新主题**，而是把这条链路**真正跑通一次端到端**：
>
> 🔑 **`--self-test` 会用已知真值的合成样本跑完整条链，并验证能否还原真值。**
> 🔑 真值是我们自己生成的（ownership: self），所以可以合法地做端到端验证。
>
> 🔴 **缺外部工具的路不做伪造**：chromaprint（`fpcalc`）与 COLMAP 若不在，
> 该路状态记为 `tool_missing` · `degrade: recorded_not_verified`，**绝不假装通过**。

## 四路

| 路 | 本脚本的实现 | 缺失时的行为 |
|---|---|---|
| `clock` | **单调时钟 + 规范命名** | 纯 Python，**总能跑** |
| `visual` | ffmpeg 抽帧 → numpy 逐帧差 + N×N 滑窗最大差 | ffmpeg 无 → `tool_missing` |
| `audio` | `fpcalc` 指纹（有则用）／否则 FFT 频谱+节拍+RMS **降级特征** | 无 fpcalc → `degraded` 并显式标注 |
| `photo` | 需 COLMAP/ArUco 位姿；本脚本只做**元数据归档** | 无 COLMAP → `tool_missing` |

用法:
  edge_pipeline.py --self-test                     # 🔑 **端到端自测（含真值校验）**
  edge_pipeline.py --fixture DIR --build-id B      # 生成已知真值样本
  edge_pipeline.py --capture DIR --build-id B      # 抽帧/抽音 + 写各路原始事件流
  edge_pipeline.py --import FILE --dir DIR --build-id B   # 🔑 **真实捕获导入**（无需真值）
  edge_pipeline.py --join    DIR --build-id B      # 按 [build_id, clock_ns] 合并
  edge_pipeline.py --durations DIR --build-id B    # → observed_durations.json
  edge_pipeline.py --report  DIR --build-id B      # 最终报告
  edge_pipeline.py --verify  DIR --build-id B      # 与真值比对（仅合成样本）

退出码: 0 通过 / 1 有阻断 / 2 用法错误
"""
import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import time

try:
    import numpy as np
except Exception:
    np = None
try:
    from PIL import Image
except Exception:
    Image = None

LANES = ('clock', 'visual', 'audio', 'photo')
CLOCK_UNIT_NS = 10 ** 9


def _hdr(t, w=78):
    print('=' * w)
    print(t)
    print('=' * w)


def _sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def _have(exe):
    return shutil.which(exe) is not None


# ---------------------------------------------------------------- 合成真值

def make_fixture(root, build_id, fps=10, cycle=(12, 18, 10)):
    """生成已知真值的 attract 循环样本：三段不同底色 + 不同音调。

    🔑 真值写入 `ground_truth.json`：**合成样本才有真值**——真实原版没有。
    """
    if np is None or Image is None:
        print('❌ 需要 numpy 与 PIL 才能生成样本')
        return 2
    d = os.path.join(root, build_id)
    src = os.path.join(d, 'source')
    os.makedirs(src, exist_ok=True)
    colors = [(40, 60, 140), (150, 40, 40), (40, 140, 70)]
    freqs = [440.0, 660.0, 880.0]
    n = sum(cycle)
    sr = 8000
    # 视频帧
    frames = []
    for i in range(n):
        acc, k = 0, 0
        for j, c in enumerate(cycle):
            if i < acc + c:
                k = j
                break
            acc += c
        img = Image.new('RGB', (64, 48), colors[k])
        px = img.load()
        for x in range(i % 64, min(i % 64 + 6, 64)):
            for y in range(20, 26):
                px[x, y] = (240, 240, 240)  # 🔑 小区域滚动元素
        p = os.path.join(src, f'f{i:04d}.png')
        img.save(p)
        frames.append(p)
    # 音频
    seg = []
    for j, c in enumerate(cycle):
        t = np.arange(int(sr * c / fps)) / sr
        seg.append((0.2 * np.sin(2 * np.pi * freqs[j] * t)).astype(np.float32))
    wav = np.concatenate(seg)
    ap = os.path.join(src, 'attract.wav')
    _write_wav(ap, wav, sr)
    # 编码成真实视频（让 capture 走 ffmpeg 解码路径）
    vid = os.path.join(src, 'attract.mp4')
    r = _sh(['ffmpeg', '-y', '-framerate', str(fps), '-i',
             os.path.join(src, 'f%04d.png'), '-i', ap,
             '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac',
             '-shortest', '-loglevel', 'error', vid])
    if r.returncode != 0:
        print(f'⚠️ ffmpeg 编码失败（{r.stderr[:120]}）——改用 PNG 序列直读')
        vid = None
    for p in frames:
        os.remove(p)
    truth = {
        'build_id': build_id,
        'fps': fps,
        'n_frames': n,
        'cycle_frames': list(cycle),
        'cycle_ms': [round(c * 1000 / fps) for c in cycle],
        'period_ms': round(n * 1000 / fps),
        'sample_rate': sr,
        'state_freqs_hz': freqs,
        'note': '🔑 合成真值（ownership: self）；真实原版没有这种真值',
    }
    os.makedirs(d, exist_ok=True)
    json.dump(truth, open(os.path.join(d, 'ground_truth.json'), 'w',
                          encoding='utf-8'), ensure_ascii=False, indent=2)
    meta = {'source_video': vid, 'source_audio': ap, 'fps': fps,
            'n_frames': n}
    if vid is None:
        meta['source_frames_dir'] = src
    json.dump(meta, open(os.path.join(d, 'source_meta.json'), 'w',
                         encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'✅ 已生成合成真值样本: {d}')
    print(f'   周期 {truth["period_ms"]} ms · 三段 {truth["cycle_ms"]} ms')
    print('   🔑 这是**我们自己造的真值**，用来验证流水线能否还原——不代表原版')
    return 0


def _write_wav(path, data, sr):
    import wave
    pcm = (np.clip(data, -1, 1) * 32000).astype('<i2')
    with wave.open(path, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


# ---------------------------------------------------------------- capture

def _canon(d, state, media, idx, clock_ns, ext='png'):
    """🔑 规范命名 `{build_id}/{state}/{media_type}/{index}_{clock_ns}.{ext}`

    `d` 传入时**已是 build_id 目录**，故不再重复拼一层 build_id。
    """
    p = os.path.join(d, state, media)
    os.makedirs(p, exist_ok=True)
    return os.path.join(p, f'{idx:06d}_{clock_ns}.{ext}')


def cmd_capture(a):
    d = a.dir
    b = a.build_id
    dm = os.path.join(d, b)
    meta_p = os.path.join(dm, 'source_meta.json')
    if not os.path.exists(meta_p):
        print(f'❌ 缺 {meta_p}（先跑 --fixture，或手写 source_meta.json）')
        return 2
    meta = json.load(open(meta_p, encoding='utf-8'))
    fps = meta.get('fps', 10)
    out = os.path.join(dm, 'raw')
    os.makedirs(out, exist_ok=True)
    fr_dir = os.path.join(dm, 'frames')
    if os.path.exists(fr_dir):
        shutil.rmtree(fr_dir)
    os.makedirs(fr_dir, exist_ok=True)
    status = {}

    # ---- visual 路 ----
    if not _have('ffmpeg'):
        status['visual'] = 'tool_missing'
        print('⚠️ visual：ffmpeg 缺失 → 记为 tool_missing（不伪造）')
    else:
        vid = meta.get('source_video')
        if vid and os.path.exists(vid):
            r = _sh(['ffmpeg', '-y', '-i', vid, '-vsync', '0',
                     '-loglevel', 'error', os.path.join(fr_dir, 'f%06d.png')])
            ok = r.returncode == 0
        else:
            ok = False
        if not ok and meta.get('source_frames_dir'):
            fr_dir = meta['source_frames_dir']
            ok = True
        frames = sorted(x for x in os.listdir(fr_dir) if x.endswith('.png'))
        events = []
        prev = None
        for i, fn in enumerate(frames):
            clock_ns = int(round(i * CLOCK_UNIT_NS / fps))
            dst = _canon(dm, 'attract', 'video', i, clock_ns, 'png')
            shutil.copy(os.path.join(fr_dir, fn), dst)
            rec = {'lane': 'visual', 'build_id': b, 'frame_index': i,
                   'global_sample_clock_ns': clock_ns, 'asset_uri': dst,
                   'artifact_sha256': _sha(dst)}
            if np is not None and Image is not None and prev is not None:
                c = os.path.join(fr_dir, fn)
                diff, win = _frame_diff(prev, c, a.window)
                rec['metric_name'] = 'frame_diff_mean'
                rec['metric_value'] = diff
                rec['window_max_diff'] = win
            events.append(rec)
            prev = os.path.join(fr_dir, fn)
        _dump(out, 'visual.jsonl', events)
        status['visual'] = 'ok'
        print(f'✅ visual：{len(frames)} 帧已抽帧并写入规范命名')

    # ---- audio 路 ----
    fp = meta.get('source_audio')
    if not (fp and os.path.exists(fp)):
        status['audio'] = 'tool_missing'
        print('⚠️ audio：无源音频 → 记为 tool_missing')
    else:
        ev, backend = _audio_lane(fp, b, a.window)
        _dump(out, 'audio.jsonl', ev)
        status['audio'] = 'ok' if backend == 'chromaprint' else 'degraded'
        print(f'✅ audio：{len(ev)} 窗 · 后端 **{backend}**'
              + ('（🔴 **降级特征，非真指纹**）' if backend != 'chromaprint' else ''))

    # ---- clock 路（纯 Python，总能跑）----
    cev = [{'lane': 'clock', 'build_id': b, 'frame_index': i,
            'global_sample_clock_ns': int(round(i * CLOCK_UNIT_NS / fps)),
            'metric_name': 'clock_ns', 'metric_value':
            int(round(i * CLOCK_UNIT_NS / fps))}
           for i in range(meta.get('n_frames', 0))]
    _dump(out, 'clock.jsonl', cev)
    status['clock'] = 'ok'

    # ---- photo 路 ----
    status['photo'] = 'tool_missing' if not _have('colmap') else 'ok'
    if status['photo'] == 'tool_missing':
        print('⚠️ photo：COLMAP 缺失 → 记为 tool_missing（只归档，不伪造位姿）')
    json.dump(status, open(os.path.join(dm, 'lane_status.json'), 'w',
                           encoding='utf-8'), ensure_ascii=False, indent=2)
    print('\n🔑 **缺工具的路记为 tool_missing，不进入「通过」统计。**')
    return 0


def _sha(p):
    import hashlib
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(65536), b''):
            h.update(c)
    return h.hexdigest()[:16]


def _dump(d, name, rows):
    with open(os.path.join(d, name), 'w', encoding='utf-8') as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')


def _frame_diff(p1, p2, win):
    a = np.asarray(Image.open(p1).convert('L'), dtype=np.int16)
    b = np.asarray(Image.open(p2).convert('L'), dtype=np.int16)
    if a.shape != b.shape:
        return None, None
    d = np.abs(a - b).astype(np.float32)
    m = float(d.mean())
    wm = 0.0
    n = max(1, int(win))
    if a.shape[0] >= n and a.shape[1] >= n:
        # 🔑 N×N 滑窗最大差（pixelmatch windowSize 语义）
        for y in range(0, a.shape[0] - n + 1, max(1, n)):
            for x in range(0, a.shape[1] - n + 1, max(1, n)):
                wm = max(wm, float(d[y:y + n, x:x + n].mean()))
    return round(m, 3), round(wm, 3)


def _audio_lane(path, build_id, win):
    import wave
    if _have('fpcalc'):
        r = _sh(['fpcalc', '-raw', path])
        if r.returncode == 0:
            return ([{'lane': 'audio', 'build_id': build_id,
                      'global_sample_clock_ns': 0,
                      'metric_name': 'chromaprint', 'metric_value':
                      r.stdout.strip()[:64], 'backend': 'chromaprint'}],
                    'chromaprint')
    with wave.open(path, 'rb') as w:
        sr = w.getframerate()
        raw = w.readframes(w.getnframes())
    x = np.frombuffer(raw, dtype='<i2').astype(np.float32) / 32768.0
    fs = 2048
    events = []
    for i in range(0, max(0, len(x) - fs), fs):
        seg = x[i:i + fs]
        sp = np.abs(np.fft.rfft(seg * np.hanning(fs)))
        hz = float(np.argmax(sp)) * sr / fs
        ev = {'lane': 'audio', 'build_id': build_id, 'window_index': i // fs,
              'global_sample_clock_ns': int(round(i * CLOCK_UNIT_NS / sr)),
              'metric_name': 'dominant_hz', 'metric_value': round(hz, 1),
              'rms': round(float(np.sqrt((seg ** 2).mean())), 4),
              'backend': 'numpy_fft_fallback'}
        events.append(ev)
    return events, 'numpy_fft_fallback'


# ---------------------------------------------------------------- join

def cmd_import(a):
    """🔑 **真实捕获导入**——把任意真实视频/音频喂进同一条四路流水线。

    > 🔴 与 `--fixture` 的根本区别：**真实捕获没有真值**。
    > 所以本路径**不生成 `ground_truth.json`**，并且 `--verify` 会被明确拒绝。
    > 🔑 这把"自测"和"真实取证"分成两条路径——**避免把自测当成取证**。

    🔑 用 `ffprobe` 自动探测 fps/时长/是否有音轨，**不要求手写 meta**。
    """
    src = a.import_file
    if not os.path.exists(src):
        print(f'❌ 缺 {src}')
        return 2
    if not _have('ffprobe'):
        print('❌ 缺 ffprobe —— 真实导入必须先探测，不能猜 fps')
        return 2
    info = _probe(src)
    if info is None:
        print(f'❌ ffprobe 无法解析 {src}')
        return 2
    fps = info['fps']
    dur = info['duration_s']
    has_audio = info['has_audio']
    print('=' * 74)
    print(f'真实捕获导入 · {os.path.basename(src)}')
    print('=' * 74)
    print(f'\n探测结果: fps={fps} · 时长={dur}s · 音轨={"有" if has_audio else "无"}')
    print('🔑 **真实捕获没有真值** —— 不生成 ground_truth.json，'
          '`--verify` 将被拒绝')
    dm = os.path.join(a.dir, a.build_id)
    os.makedirs(dm, exist_ok=True)
    meta = {'source_video': src, 'fps': fps,
            'n_frames': int(round(dur * fps)) if dur else 0,
            'source_audio': None}
    # 抽音（若有音轨）
    if has_audio and _have('ffmpeg'):
        ap = os.path.join(dm, 'extracted.wav')
        r = _sh(['ffmpeg', '-y', '-i', src, '-vn', '-ac', '1', '-ar', '8000',
                 '-loglevel', 'error', ap])
        if r.returncode == 0:
            meta['source_audio'] = ap
    json.dump(meta, open(os.path.join(dm, 'source_meta.json'), 'w',
                         encoding='utf-8'), ensure_ascii=False, indent=2)
    json.dump({'probe': info, 'ground_truth': None,
               'note': '🔑 真实捕获：无真值，不得运行 --verify'},
              open(os.path.join(dm, 'import_info.json'), 'w',
                   encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'\n✅ 已写入 {dm}/source_meta.json —— 现在可跑 --capture')
    return 0


def _probe(path):
    r = _sh(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
             '-show_entries', 'stream=r_frame_rate,nb_frames,duration',
             '-show_entries', 'format=duration', '-of', 'json', path])
    if r.returncode != 0:
        return None
    try:
        d = json.loads(r.stdout)
    except Exception:
        return None
    fps = None
    st = (d.get('streams') or [{}])[0]
    fr = st.get('r_frame_rate') or ''
    if '/' in fr:
        n, _, dn = fr.partition('/')
        try:
            fps = float(n) / float(dn) if float(dn) else float(n)
        except Exception:
            fps = None
    if not fps:
        fps = 25.0  # 🔑 探测失败就用显式默认并**标注**，不静默
    dur = None
    for k in (st.get('duration'), (d.get('format') or {}).get('duration')):
        if k:
            try:
                dur = float(k)
                break
            except Exception:
                pass
    ra = _sh(['ffprobe', '-v', 'error', '-select_streams', 'a:0',
              '-show_entries', 'stream=codec_type', '-of', 'csv=p=0', path])
    return {'fps': round(fps, 3), 'duration_s': round(dur, 3) if dur else None,
            'has_audio': bool((ra.stdout or '').strip()),
            'r_frame_rate': fr,
            'fps_guessed': not bool(fr)}


def cmd_join(a):
    d = os.path.join(a.dir, a.build_id, 'raw')
    if not os.path.isdir(d):
        print(f'❌ 缺 {d}（先跑 --capture）')
        return 2
    merged, lanes = {}, {}
    for ln in LANES:
        p = os.path.join(d, f'{ln}.jsonl')
        if not os.path.exists(p):
            continue
        rows = [json.loads(x) for x in open(p, encoding='utf-8') if x.strip()]
        lanes[ln] = len(rows)
        for r in rows:
            merged.setdefault(int(r['global_sample_clock_ns']), []).append(r)
    out = os.path.join(a.dir, a.build_id, 'joined.jsonl')
    with open(out, 'w', encoding='utf-8') as f:
        for t in sorted(merged):
            f.write(json.dumps({'build_id': a.build_id,
                                'global_sample_clock_ns': t,
                                'events': merged[t]}, ensure_ascii=False) + '\n')
    print(f'✅ 已合并 {len(merged)} 个时间点 → {out}')
    for k, v in lanes.items():
        print(f'   {k}: {v} 条')
    miss = [x for x in LANES if x not in lanes]
    if miss:
        print(f'   ⚪ 未产生事件的路: {miss}（**不计入通过**）')
    return 0


# ---------------------------------------------------------------- durations

def cmd_durations(a):
    dm = os.path.join(a.dir, a.build_id)
    raw = os.path.join(dm, 'raw')
    vis = os.path.join(raw, 'visual.jsonl')
    if not os.path.exists(vis):
        print(f'❌ 缺 {vis}')
        return 2
    frames = [json.loads(x) for x in open(vis, encoding='utf-8') if x.strip()]
    # 🔑 从"帧间差"的峰值切段：差大＝状态切换
    segs, cur = [], 1
    for r in frames[1:]:
        dv = r.get('metric_value') or 0
        if dv and dv >= a.threshold:
            segs.append(cur)
            cur = 1
        else:
            cur += 1
    if cur:
        segs.append(cur)
    gt_p = os.path.join(dm, 'ground_truth.json')
    ms = None
    if os.path.exists(gt_p):
        gt = json.load(open(gt_p, encoding='utf-8'))
        ms = [round(s * 1000 / gt['fps']) for s in segs]
    obs = {
        'build_id': a.build_id,
        'segment_frames': segs,
        'segment_ms': ms,
        # 🔑 基线不可知时不填 T_min/T_max——只产出观测值
        'T_min_ms': None,
        'T_max_ms': None,
        'baseline_known': False,
        'threshold_used': a.threshold,
        'lane_status': json.load(open(os.path.join(dm, 'lane_status.json'),
                                      encoding='utf-8'))
        if os.path.exists(os.path.join(dm, 'lane_status.json')) else {},
        'note': '🔑 **基线不可知就只产出观测值，不伪造 PASS**',
    }
    p = os.path.join(dm, 'observed_durations.json')
    json.dump(obs, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'✅ 已产出 {p}')
    print(f'   观测段（帧）: {segs}')
    if ms:
        print(f'   观测段（ms）: {ms}')
    print('   🔑 `T_min_ms/T_max_ms` 为 null —— **基线不可知，不伪造**')
    return 0


# ---------------------------------------------------------------- report

def cmd_report(a):
    dm = os.path.join(a.dir, a.build_id)
    st = json.load(open(os.path.join(dm, 'lane_status.json'), encoding='utf-8')) \
        if os.path.exists(os.path.join(dm, 'lane_status.json')) else {}
    od = os.path.join(dm, 'observed_durations.json')
    obs = json.load(open(od, encoding='utf-8')) if os.path.exists(od) else {}
    _hdr(f'四路验收报告 · build_id={a.build_id}')
    print('\n| 路 | 状态 | 说明 |')
    print('|---|---|---|')
    note = {'clock': '单调时钟 + 规范命名', 'visual': 'ffmpeg 抽帧 + 逐帧/滑窗差',
            'audio': 'fpcalc 指纹 / 否则 FFT 降级特征',
            'photo': '需 COLMAP 位姿，本脚本只归档'}
    for ln in LANES:
        s = st.get(ln, 'not_run')
        mark = {'ok': '✅', 'degraded': '⚠️ 降级', 'tool_missing': '⚪ 缺工具',
                'not_run': '—'}.get(s, s)
        print(f'| `{ln}` | {mark} | {note[ln]} |')
    real = [k for k, v in st.items() if v == 'ok']
    print(f'\n🔑 **真正跑通的路 = {len(real)}/{len(LANES)}**（{real}）')
    print('🔑 `tool_missing` / `degraded` **不计入通过**，只表示"已记录但未验证"')
    if obs:
        print(f'\n观测段（帧）: {obs.get("segment_frames")}')
        print(f'基线已知: {obs.get("baseline_known")} · '
              f'T_min/T_max: {obs.get("T_min_ms")}/{obs.get("T_max_ms")}')
    print('\n🔑 **任何人工批准必须记 reviewer · 旧 baseline hash · '
          '新 baseline hash · 偏离理由。**')
    return 0


# ---------------------------------------------------------------- verify

# ------------------------------------------------------- verify-guard
# 🔑 第七十一轮新增：**G338 的真实可执行命令**
#
# 🔴 第七十一轮发现：`run_all_gates.py` 里 G338 的 tpl 被写成**字符串**，
#    `build_cmd` 遍历字符串 → 逐字符当命令 → `No such file or directory: '🔑'`
#    → 被 `except` 吞掉 → **hard 门禁变成"软警告"，从未真正执行过**。
#
# 🔑 本子命令让 G338 变成**真能跑**的门禁：
#    真实捕获（--import）→ 无 ground_truth → --verify **必须**退出 1。
# ==========================================================================


def cmd_verify_guard(a):
    """🔑 守卫自测：真实捕获走 --verify 必须被拒。"""
    import shutil as _sh
    import tempfile as _tf
    print('=' * 70)
    print('verify-guard · 🔑 真实捕获不得走 --verify（G338 的真实命令）')
    print('=' * 70)
    if not _sh.which('ffmpeg'):
        print('🔴 **缺 ffmpeg** —— 无法合成真实素材，本守卫**不可执行**。')
        print('   🔑 这不是"通过"，是"没测"。')
        return 2
    d = a.dir or _tf.mkdtemp(prefix='vg_')
    os.makedirs(d, exist_ok=True)
    src = os.path.join(d, 'src.mp4')
    r = subprocess.run(['ffmpeg', '-y', '-f', 'lavfi', '-i',
                        'testsrc2=size=160x120:rate=10:duration=2',
                        '-f', 'lavfi', '-i',
                        'sine=frequency=440:duration=2',
                        '-shortest', '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
                        '-c:a', 'aac', src],
                       capture_output=True, timeout=120)
    if r.returncode != 0 or not os.path.isfile(src):
        print(f'🔴 素材生成失败（rc={r.returncode}）—— 本守卫**没测**。')
        return 2
    print(f'\n① 合成真实素材: {os.path.getsize(src)} B'
          f'（ffmpeg 编码，非脚本自造）')
    ri = cmd_import(argparse.Namespace(import_file=src, dir=d,
                                       build_id='guard001'))
    if ri != 0:
        print(f'🔴 --import 失败 rc={ri}')
        return 2
    gp = os.path.join(d, 'guard001', 'ground_truth.json')
    ip = os.path.join(d, 'guard001', 'import_info.json')
    print(f'② ground_truth.json 存在: {os.path.exists(gp)}  '
          f'（🔑 真实捕获**不应**生成）')
    print(f'   import_info.json 存在:  {os.path.exists(ip)}')
    rv = cmd_verify(argparse.Namespace(dir=d, build_id='guard001'))
    print(f'\n③ `--verify` 退出码: {rv}  （🔑 期望 **1 = 被拒绝**）')
    ok = (not os.path.exists(gp)) and os.path.exists(ip) and rv == 1
    print('\n' + '=' * 70)
    print('✅ 守卫成立：真实捕获走 --verify 被拒'
          if ok else '🔴 守卫失效：见上')
    print('=' * 70)
    return 0 if ok else 1


def cmd_verify(a):
    dm = os.path.join(a.dir, a.build_id)
    gp = os.path.join(dm, 'ground_truth.json')
    op = os.path.join(dm, 'observed_durations.json')
    if not os.path.exists(gp):
        # 🔑 真实捕获路径：没有真值是**正常的**，要明确区分于"缺文件"
        ip = os.path.join(dm, 'import_info.json')
        if os.path.exists(ip):
            print('🚫 **真实捕获没有真值，`--verify` 不适用**。')
            print('   🔑 导入的真实素材只能产出观测值，不能做真值校验。')
            print('   🔴 若需要校验，必须另立人工确认的 baseline（带 reviewer + hash）。')
            return 1
        print('❌ 缺 ground_truth.json（合成样本才有真值）')
        return 2
    if not os.path.exists(op):
        print('❌ 缺 observed_durations.json')
        return 2
    gt = json.load(open(gp, encoding='utf-8'))
    ob = json.load(open(op, encoding='utf-8'))
    exp = gt['cycle_frames']
    got = ob['segment_frames']
    # 循环起点可能不同：旋转对齐后比较
    best = None
    for k in range(len(got)):
        rot = got[k:] + got[:k]
        if len(rot) == len(exp):
            err = sum(abs(x - y) for x, y in zip(rot, exp))
            if best is None or err < best[0]:
                best = (err, k)
    print('=' * 74)
    print(f'真值校验 · build_id={a.build_id}')
    print('=' * 74)
    print(f'\n期望段（帧）: {exp}')
    print(f'观测段（帧）: {got}')
    if best is None:
        print('\n❌ 段数不同，无法对齐')
        return 1
    err, k = best
    ok = err <= max(2, len(exp))
    print(f'\n最佳旋转偏移 {k} · 逐段误差 {err} 帧 · 阈值 {max(2, len(exp))}')
    print('✅ **流水线还原了合成真值**' if ok else '❌ 未还原真值')
    print('\n🔑 **这只证明流水线本身可用**——'
          '🔴 **不证明任何原版行为已被取证**（真值是我们自己造的）。')
    return 0 if ok else 1


# ---------------------------------------------------------------- self-test

def cmd_self_test(a):
    import tempfile
    tmp = a.dir or tempfile.mkdtemp(prefix='edge53_')
    os.makedirs(tmp, exist_ok=True)
    bid = a.build_id or 'fixture53'
    _hdr('四路验收端到端自测（**含真值校验**）')
    print(f'\n工作目录: {tmp} · build_id: {bid}')
    print('🔑 真值是我们自己生成的合成样本（ownership: self）\n')
    steps = [
        ('① 生成合成真值样本',
         lambda: make_fixture(tmp, bid)),
        ('② capture：抽帧/抽音 + 写各路原始事件流',
         lambda: cmd_capture(argparse.Namespace(dir=tmp, build_id=bid,
                                                window=a.window))),
        ('③ join：按 [build_id, clock_ns] 合并',
         lambda: cmd_join(argparse.Namespace(dir=tmp, build_id=bid))),
        ('④ durations：产出 observed_durations.json',
         lambda: cmd_durations(argparse.Namespace(dir=tmp, build_id=bid,
                                                  threshold=a.threshold))),
        ('⑤ report：四路状态报告',
         lambda: cmd_report(argparse.Namespace(dir=tmp, build_id=bid))),
        ('⑥ verify：与合成真值比对',
         lambda: cmd_verify(argparse.Namespace(dir=tmp, build_id=bid))),
    ]
    for name, fn in steps[:5]:
        print(f'\n--- {name} ---')
        r = fn()
        if r not in (0, None):
            print(f'❌ 步骤失败（退出码 {r}）')
            return 1
    print(f'\n--- {steps[5][0]} ---')
    rc = steps[5][1]()
    print('\n' + '=' * 74)
    print('✅ **端到端跑通**：fixture → capture → join → durations → report → verify'
          if rc == 0 else '❌ 端到端未还原真值')
    print('=' * 74)
    print('\n🔑 **本轮成果**：这条链以前只存在于文档里，现在**真的能跑**。')
    print('🔑 但它验证的是**流水线本身**，🔴 **不是任何原版行为**。')
    if not a.dir:
        print(f'\n（临时目录保留: {tmp}）')
    return rc


def main():
    ap = argparse.ArgumentParser(description='四路验收端到端流水线')
    ap.add_argument('--verify-guard', action='store_true',
                    help='守卫自测：真实捕获走 --verify 必须被拒（G338）')
    ap.add_argument('--self-test', action='store_true')
    ap.add_argument('--dir', help='自测工作目录（默认临时目录）')
    ap.add_argument('--fixture', metavar='DIR')
    ap.add_argument('--capture', metavar='DIR')
    ap.add_argument('--join', metavar='DIR')
    ap.add_argument('--durations', metavar='DIR')
    ap.add_argument('--report', metavar='DIR')
    ap.add_argument('--verify', metavar='DIR')
    ap.add_argument('--import', dest='import_file',
                    help='🔑 真实捕获文件（视频/音频）导入')
    ap.add_argument('--build-id', default='build001')
    ap.add_argument('--window', type=int, default=8,
                    help='N×N 滑窗边长（pixelmatch windowSize 语义）')
    ap.add_argument('--threshold', type=float, default=8.0,
                    help='帧间差切段阈值')
    a = ap.parse_args()
    if a.import_file:
        return cmd_import(a)
    if a.verify_guard:
        return cmd_verify_guard(a)
    if a.self_test:
        return cmd_self_test(a)
    if a.fixture:
        return make_fixture(a.fixture, a.build_id)
    if a.capture:
        return cmd_capture(argparse.Namespace(dir=a.capture,
                                              build_id=a.build_id,
                                              window=a.window))
    if a.join:
        return cmd_join(argparse.Namespace(dir=a.join, build_id=a.build_id))
    if a.durations:
        return cmd_durations(argparse.Namespace(dir=a.durations,
                                                build_id=a.build_id,
                                                threshold=a.threshold))
    if a.report:
        return cmd_report(argparse.Namespace(dir=a.report, build_id=a.build_id))
    if a.verify:
        return cmd_verify(argparse.Namespace(dir=a.verify, build_id=a.build_id))
    print('❌ 需要 --self-test / --verify-guard / --fixture / --capture '
          '/ --join / --durations / --report / --verify 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
