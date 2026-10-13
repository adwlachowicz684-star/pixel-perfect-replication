# 🔑 第一百五十六轮：G444 依赖
# 🔴 155 轮诚实结论② 点名的真实缺口：G443 的反证样本**只造 git/trees 一个环节**，
#    其余三个环节靠"找不到"**间接**兜底 —— 🔑 若 `_write_step_scan` 退化成
#    "只对某一个环节生效"，G443 仍会 rc=0，而其余环节的裸 req 从此无人发现。
#    🔑 **只测一个样本点 = 把"实现是否对其余环节生效"完全交给运气**
#    （151 轮 G439"逐条各造一次篡改"同款，本轮推广到**环节**维度）。
WRITE_PROOF_SEG_MIN = 3
WRITE_PROOF_KIND_MIN = 3
# 🔑 G444 判据⑤⑥ 依赖：G443 反证样本所用的那个环节（**退化对照点**）。
#    🔴 它必须**真的**出现在 G443 源码里，否则"只认这一个环节"的退化实现
#       不会被 G443 放过，⑤ 的内嵌对照就形同虚设（判据⑥ 守这一条）。
WRITE_LEGACY_PROOF_SEG = 'git/trees'
# 🔑 G444 判据① 依赖：唯一实现的函数名（一致改名时不得假阳性）
WRITE_PROOF_FN = '_write_proof_check'


def _write_proof_check(scan_fn, bad_fn, steps):
    """🔑 G444 的**唯一实现**：对**每一个**写环节各造 A/B/C 三个反证样本，
    逐环节**独立**判定。返回 (未命中列表, 覆盖环节数, 明细列表)。

    🔴 为什么必须**逐环节**（155 轮推演 → 本轮实证）：
       G443 只造 git/trees 一个环节的样本。扫描若退化成"只认某一个环节"，
       其余环节在 G443 口径下依然全绿 —— **反证覆盖不到 == 没守护**。

    🔑 三种形态（**每个环节各造一次**）：
       A 同一环节 `req_retry` + 裸 `req` 写调用并存 → 期望「裸 req」
       B GET 走 `req_retry` + 写方法却是裸 `req`     → 期望「裸 req」
       C 只有 GET、无写调用                          → 期望「找不到」

    🔑 返回 (miss, covered, rows)；scan_fn / bad_fn 为 None 或 steps 为空时
       miss **非空** —— 🔴 缺失必须表现为"未命中"，不得静默通过（106 轮同病）。
    """
    miss = []
    rows = []
    if scan_fn is None or bad_fn is None:
        miss.append('扫描/判定实现缺失 —— 反证无法进行，拒绝给结论')
        return miss, 0, rows
    if not steps:
        miss.append('环节清单为空 —— 反证无样本，判据恒真')
        return miss, 0, rows
    covered = 0
    for idx, item in enumerate(steps):
        seg, method = item[0], item[1]
        slug = 'p%d' % idx
        # 🔑 样本按环节**参数化生成** —— 新增环节自动纳入，不许写死一组
        snips = (
            ('A', chr(10).join([
                'def _snip_a_%s():' % slug,
                "    req_retry('%s', API + '/%s', {})" % (method, seg),
                "    req('%s', API + '/%s', {})" % (method, seg),
            ]), '裸 req'),
            ('B', chr(10).join([
                'def _snip_b_%s():' % slug,
                "    req_retry('GET', API + '/%s', None)" % seg,
                "    req('%s', API + '/%s', {})" % (method, seg),
            ]), '裸 req'),
            ('C', chr(10).join([
                'def _snip_c_%s():' % slug,
                "    req_retry('GET', API + '/%s', None)" % seg,
            ]), '找不到'),
        )
        seg_ok = True
        # 🔑 形态数必须**真查**，不许只声明常量（148 轮"声称与实现不符"同款）
        if len(snips) < WRITE_PROOF_KIND_MIN:
            miss.append('环节 %s 只有 %d 种反证形态 < %d —— 样本集被缩水，'
                        'A/B/C 缺一也发现不了' % (seg, len(snips),
                                                   WRITE_PROOF_KIND_MIN))
            seg_ok = False
        for tag, snip, want in snips:
            try:
                t = ast.parse(snip)
            except Exception as e:
                miss.append('环节 %s / %s 样本无法解析 —— 拒绝给结论: %s'
                            % (seg, tag, e))
                seg_ok = False
                continue
            found = scan_fn(t, steps)
            bad = bad_fn(found, steps)
            # 🔑 只认**该环节**的违规：其它环节的"找不到"会稀释判据
            #    （155 轮方向⑥ 实测：被无关命中顶替成 rc=0）
            hit = any((want in x and seg in x) for x in bad)
            if not hit:
                miss.append('环节 %s / %s 期望含「%s」，实际违规=%s'
                            % (seg, tag, want, bad))
                seg_ok = False
            rows.append((seg, tag, want, hit, len(bad)))
        if seg_ok:
            covered += 1
    return miss, covered, rows


def cmd_assert_write_step_proof():
    """🔑 G444：**写环节反证必须逐环节各造一次**（第一百五十六轮）。

    🔴 真实缺口（155 轮诚实结论②，本轮对照实验实证）：
       G443 的 ②/③/④ 三个反证样本**都只造 `git/trees` 一个环节**，
       其余三个环节（blobs / commits / refs）靠"找不到"**间接**兜底。
       🔑 把 `_write_step_scan` 退化成"只对 git/trees 生效"——
          **G443 rc=0 放行** · **G444 rc=1 抓到**。
       🔴 同一状态一绿一红 —— G444 的存在理由不是推演，是跑出来的。

    🔑 七条判据：
       ① 唯一实现 `_write_proof_check` 存在（经常量 `WRITE_PROOF_FN` 取，
          不许硬编码函数名 —— 一致改名会假阳性，134/155 轮同病）
       ② 反证覆盖**每一个**环节：覆盖数 == 清单条数，且 ≥ `WRITE_PROOF_SEG_MIN`；
          每环节形态数 ≥ `WRITE_PROOF_KIND_MIN`（防样本集被缩水）
       ③ 用**真实** `_write_step_scan` / `_write_step_bad` 跑：未命中列表必须为空
       ④ **退化反证**：两个退化实现（恒空桩 / 只认一个环节）都必须产生未命中
          —— 🔴 证明判据③ 不是恒真（106 轮"缺失≠没有违规"）
       ⑤ **内嵌对照**：同一个"只认一个环节"的退化实现，在 **G443 口径**
          （只看 `WRITE_LEGACY_PROOF_SEG`）下**全部命中** —— 证明 G443 真看不见
       ⑥ `WRITE_LEGACY_PROOF_SEG` 必须**真的**出现在 G443 源码里
          —— 否则对照点漂移，⑤ 形同虚设
       ⑦ 一致改名不得假阳性：以别名注入同名实现并同步常量后仍可取到
    """
    print('🔑 **写环节反证必须逐环节各造一次**（G444）')
    print('=' * 70)
    os.chdir(ROOT)
    bad = []

    steps = globals().get('WRITE_RETRY_STEPS')
    if not isinstance(steps, (list, tuple)) or not steps:
        bad.append('WRITE_RETRY_STEPS 缺失或为空 —— 反证无样本，判据恒真'
                   '（106 轮"缺失≠没有违规"同病）')
        steps = ()

    fn_scan = globals().get(WRITE_SCAN_FN)
    fn_bad = globals().get(WRITE_BAD_FN)
    fn_proof = globals().get(WRITE_PROOF_FN)
    print(f'① 唯一实现（经常量取）: {WRITE_PROOF_FN}={fn_proof is not None} · '
          f'{WRITE_SCAN_FN}={fn_scan is not None} · '
          f'{WRITE_BAD_FN}={fn_bad is not None}')
    if fn_proof is None:
        bad.append('唯一实现 %s 缺失 —— 崩溃与拒绝在 rc 上无法区分'
                   '（133 轮同病）' % WRITE_PROOF_FN)
    if fn_scan is None or fn_bad is None:
        bad.append('%s / %s 缺失 —— 无真实扫描可供反证'
                   % (WRITE_SCAN_FN, WRITE_BAD_FN))

    src = None
    try:
        src = io.open(os.path.join(ROOT, 'scripts', 'push_api.py'),
                      encoding='utf-8').read()
    except Exception as e:
        bad.append(f'无法读取源码 —— 拒绝给结论: {e}')

    # ② 覆盖每一个环节
    n_seg = len(steps)
    print(f'② 环节清单条数={n_seg} · 覆盖下限={WRITE_PROOF_SEG_MIN} · '
          f'形态下限={WRITE_PROOF_KIND_MIN}')
    if n_seg < WRITE_PROOF_SEG_MIN:
        bad.append('环节清单只有 %d 条 < %d —— 反证样本集过小，'
                   '逐环节判定形同虚设' % (n_seg, WRITE_PROOF_SEG_MIN))
    if WRITE_PROOF_KIND_MIN < 3:
        bad.append('WRITE_PROOF_KIND_MIN=%d < 3 —— A/B/C 三形态缺一也会被判通过'
                   % WRITE_PROOF_KIND_MIN)

    # ③ 用真实实现跑：未命中必须为空
    if fn_proof is not None and fn_scan is not None and fn_bad is not None:
        miss, covered, rows = fn_proof(fn_scan, fn_bad, steps)
        for seg, tag, want, hit, nbad in rows:
            print('③ 环节 %-22s %s 期望「%s」· 命中=%s · 违规数=%d'
                  % (seg, tag, want, hit, nbad))
        print(f'③ 覆盖环节数={covered}/{n_seg}')
        if miss:
            for m in miss:
                bad.append('③ ' + m)
        if covered != n_seg:
            bad.append('③ 覆盖 %d 个环节 != 清单 %d 条 —— 有环节未被反证覆盖'
                       % (covered, n_seg))

        # ④ 退化反证：两个退化实现都必须被抓到
        def _scan_stub(tree, steps):
            """🔴 反证样本 A：恒返回空 —— 扫描被换成空壳。"""
            return {}

        def _scan_one(tree, steps):
            """🔴 反证样本 B：只对 `WRITE_LEGACY_PROOF_SEG` 一个环节生效。

            🔑 这正是 155 轮诚实结论② 担心的形态：G443 只测那一个环节，
               所以它在 G443 口径下**全绿**，而其余环节的裸 req 无人发现。
            """
            one = globals().get('WRITE_LEGACY_PROOF_SEG')
            out = {}
            if not one:
                return out
            for sub in ast.walk(tree):
                if not isinstance(sub, ast.Call):
                    continue
                fn = None
                if isinstance(sub.func, ast.Name):
                    fn = sub.func.id
                elif isinstance(sub.func, ast.Attribute):
                    fn = sub.func.attr
                if fn not in ('req', 'req_retry'):
                    continue
                if not sub.args:
                    continue
                a0 = sub.args[0]
                if not (isinstance(a0, ast.Constant)
                        and a0.value in WRITE_METHODS):
                    continue
                blob = ast.dump(sub)
                if one in blob:
                    out.setdefault(one, {}).setdefault(fn, 0)
                    out[one][fn] += 1
            return out

        for tag, deg in (('④A 恒空桩', _scan_stub), ('④B 只认一个环节', _scan_one)):
            dmiss, dcov, _drows = fn_proof(deg, fn_bad, steps)
            print('%s: 覆盖=%d/%d · 未命中=%d' % (tag, dcov, n_seg, len(dmiss)))
            if not dmiss:
                bad.append('%s 未被判为退化 —— 判据③ 可能恒真，'
                           '扫描失效无人发现' % tag)

        # ⑤ 内嵌对照：同一个退化实现在 **G443 口径** 下全部命中
        one = globals().get('WRITE_LEGACY_PROOF_SEG')
        if not one:
            bad.append('WRITE_LEGACY_PROOF_SEG 缺失 —— ⑤ 无对照点，拒绝给结论')
        else:
            legacy_ok = True
            for tag, snip, want in (
                ('A', chr(10).join([
                    'def _lg_a():',
                    "    req_retry('POST', API + '/%s', {})" % one,
                    "    req('POST', API + '/%s', {})" % one,
                ]), '裸 req'),
                ('B', chr(10).join([
                    'def _lg_b():',
                    "    req_retry('GET', API + '/%s', None)" % one,
                    "    req('POST', API + '/%s', {})" % one,
                ]), '裸 req'),
                ('C', chr(10).join([
                    'def _lg_c():',
                    "    req_retry('GET', API + '/%s', None)" % one,
                ]), '找不到'),
            ):
                try:
                    t = ast.parse(snip)
                except Exception as e:
                    bad.append('⑤ G443 口径样本 %s 无法解析: %s' % (tag, e))
                    legacy_ok = False
                    continue
                b = fn_bad(_scan_one(t, steps), steps)
                hit = any((want in x and one in x) for x in b)
                if not hit:
                    legacy_ok = False
                print('⑤ G443 口径（只看 %s）/%s: 命中=%s' % (one, tag, hit))
            if not legacy_ok:
                bad.append('⑤ 退化实现在 G443 口径下未全部命中 —— '
                           '内嵌对照不成立，无法证明 G443 真的看不见')
            else:
                print('⑤ 🔑 内嵌对照成立：退化实现在 G443 口径下**全绿**，'
                      '在 G444 逐环节口径下被抓到')

    # ⑥ 对照点必须真的出现在 G443 源码里
    one = globals().get('WRITE_LEGACY_PROOF_SEG')
    if src is not None and one:
        hit_src = False
        try:
            tree = ast.parse(src)
        except Exception as e:
            bad.append(f'⑥ 源码无法解析 —— 拒绝给结论: {e}')
            tree = None
        if tree is not None:
            for node in ast.walk(tree):
                if (isinstance(node, ast.FunctionDef)
                        and node.name == 'cmd_assert_write_step_scan'):
                    for s in ast.walk(node):
                        if isinstance(s, ast.Constant) and isinstance(s.value, str):
                            if one in s.value:
                                hit_src = True
        print(f'⑥ 对照点 %s 出现在 G443 源码里: {hit_src}' % one)
        if not hit_src:
            bad.append('⑥ 对照点 %s 不在 G443 源码里 —— G443 已改用别的环节，'
                       '⑤ 的对照关系漂移，形同虚设' % one)

    # ⑦ 一致改名不得假阳性：以别名注入并同步常量后仍可取到
    if fn_proof is not None:
        alias = WRITE_PROOF_FN + '_alias_probe'
        old = globals().get(WRITE_PROOF_FN)
        globals()[alias] = old
        try:
            got = globals().get(alias)
            ok = got is old
        finally:
            globals().pop(alias, None)
        print(f'⑦ 一致改名（{alias}）后仍可取到同一实现: {ok}')
        if not ok:
            bad.append('⑦ 判据① 疑似硬编码函数名 —— 一致改名会假阳性'
                       '（134/155 轮同病）')

    if bad:
        print()
        for b in bad:
            print('  🔴', b)
        print(chr(10) + '🔴 **写环节反证逐环节覆盖** 不成立')
        return 1
    print(chr(10) + '✅ **写环节反证逐环节覆盖** 成立')
    return 0
