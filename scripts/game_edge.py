#!/usr/bin/env python3
"""试玩机/Kiosk · 反盗版屏与故意异常 · Credits 证据链
（第五十轮 A–C）。

**🔑 本轮不横向扩张，只把上一轮锁定的三张状态图挖到「可录制 · 可断言 ·
可回放」的字段层。**
> 🔑 共同性质：**它们都是"原版真实存在、但通常不被认为是游戏内容"的状态表面。**

⚠️ **边界声明**：本脚本**不吸收任何规避 · 破解 · 密钥提取 · 模拟正版环境或
绕过检查的工具/脚本**，也不把检测机制写成可执行逻辑。
**只记录可见表现 · 触发状态 · 美术 · 文案 · 音效 · 持续时间 ·
退出路径 · 版本 · 区域。**

用法:
  game_edge.py --kiosk    # 🔑 **试玩机不是零售版换皮，是独立产品状态链**
  game_edge.py --timer    # **倒计时是一套逐渐加压的中断流程**
  game_edge.py --hw       # **硬件是内容的一部分，磨损反向定义体验**
  game_edge.py --variant  # **Kiosk 版内容差异是分支版本，不是 bug**
  game_edge.py --antip    # 🔑 **失败屏是完整表现资产**
  game_edge.py --anomaly  # **故意错误内容是最容易被判成 bug 的 must-match**
  game_edge.py --cdkey    # 🔑 **CD-KEY 是字符消歧问题，不是任意字符串**
  game_edge.py --region   # **区域与介质提示要逐版逐地区逐语言核对**
  game_edge.py --credit   # 🔑 **Credits 是版本化证据链，不是美术文案**
  game_edge.py --scroll   # **滚动是精确时序**
  game_edge.py --hidden   # **隐藏内容是 Credits 状态的后继节点**
  game_edge.py --thanks   # **支持者名单最容易发生"善意的破坏"**
  game_edge.py --evolve   # **Credits 演化是补丁考古，不是美术微调**
  game_edge.py --verify   # 🔑 **"不可验证"要显式升级为字段值**
  game_edge.py --init ledger/edge50.csv
  game_edge.py --check ledger/edge50.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔑 A Kiosk
KIOSK_RULE = '🔑 **试玩机同时拥有软件形态 · 硬件形态与运维仪式，三者缺一不可。**'
KIOSK_LOOP = '上电或看门狗恢复后**开机自启** → **Attract 序列** → '
'等待投币或触摸 → **限定会话** → 空闲后返回 Attract；'
'🔑 **店员侧另有后门键序列 · 服务菜单 · 免费玩开关 · 硬重置**'
ANDROID_EG = '🔑 官方零售演示样本：🔑 **禁用键盘锁 · 快捷设置及部分全局设置**，'
'防止用户破坏演示完整性；🔑 **90 秒无操作弹窗询问退出或继续**；'
'🔑 **若选择退出或无响应 5 秒，就移除当前演示用户 · 创建新演示用户 · '
'再次播放原始视频**；🔑 **退出时静音并复位亮度 · 自动旋转 · 手电筒 · '
'语言 · 无障碍等设置**'
KIOSK_CLEAR = '🔑 这套"**完整清场**"在零售机上已经成立，街机或店铺展示机只会更重：'
'**关电重开 · 程序异常 · 观看者离开，都应以同一状态语义回到 Attract，'
'🔴 而不是回到上次进度**'
ATTRACT_LOOP = '🔑 **Attract 不是单一待机画面，而是逐帧可比的演示剪辑** —— '
'可在启动后运行，也可在游戏结束 · 设备空闲后回到该循环；'
'含标题 · 版权与厂商 · 高分 · 角色或玩法说明 · 玩法演示 · 投币/免币消息，'
'🔑 部分作品还会发出 **Attract Sound**'
HISCORE_3 = '🔑 高分表要拆成三件事：**本轮高分 · 历史高分 · 断电是否保留**。'
'🔴 **避免把断电清零误记成功能、把会持久化的高分误记成每局重算**'
TIMER_RULE = '🔑 **倒计时不是 HUD 数字，而是一套逐渐加压的中断流程。**'
TIMER_FIELDS = '初始可用时间 · 显示位置与对齐 · 是否显示币数 · '
'是否显示"还剩 N 秒" · **最后 10 秒是否变色/闪烁/增加提示音** · '
'到期时是否先弹"再投一枚" · 拒绝后等待多少帧 · '
'🔑 **中断点是暂停还是强制结束** · 已得分是否进入高分表 · '
'是否强制回到 Attract · **Attract 先播哪一屏** · '
'**是否在超时瞬间锁住操作**'
TIMER_MORE = '🔑 **"给出宽限—等待输入—超时清场"应成为默认状态，'
'🔴 而不是一超时立刻黑屏**'
HW_RULE = '🔑 **硬件是内容的一部分，磨损会反向定义游玩体验。**'
HW_FIELDS = '外壳材质 · 漆面 · **贴纸层** · logo · **灯箱颜色与亮度** · '
'**投币口灯颜色** · **灯是否闪烁** · 投币阻尼 · 退币键 · 机柜锁 · '
'防拆封条 · 螺丝位置 · 线缆走线 · 挡板 · 限制器'
HW_PANEL = '🔑 控制面板：**按键高度 · 键帽字形 · **被磨平的字符** · '
'**摇杆防尘圈磨损** · Start 键颜色 · **Service 键盲点** · 耳机插孔 · '
'投屏输出 · **屏幕烧残**'
HW_EXPO = '🔑 展会版另加：**工作人员重置频率 · 排队人数显示 · 是否有引导员 · '
'单局时限 · 超时后的控制器回收 · **手柄线被拉断后的应急接法** · '
'备用手柄切换 · 排队提示是否有多语言**'
VARIANT_RULE = '🔑 **Kiosk 版的内容差异必须当作分支版本，而不是零售版 bug。**'
VARIANT_FIELDS = '是否使用**专门展示关卡** · 是否删关 · '
'是否解锁更多内容以吸引玩家 · 难度是否更友好或更难 · 敌人生成是否被压缩 · '
'相机是否更主动 · **画面亮度/对比/色温是否被调高** · 音量是否被统一 · '
'是否禁用联网 · 是否禁用存档/成就 · 是否强制竖屏或双屏 · '
'**是否允许工作人员直接跳过**'
EXPO_FIELDS = '🔑 展会版增加"**感谢试玩** / Thank You / 工作人员联系信息 / '
'下一站信息 / 二维码 / 排队提示 / **录屏时间戳**"，'
'🔑 并核对 5 分钟限制是**从开始计时 · 首次操作后计时 · 还是倒计时暂停**'

# 🔑 B 反盗版
AP_RULE = '🔑 **失败屏是完整的表现资产，不能替换成抽象错误。**'
AP_FIELDS = '触发时刻（启动 · 读盘 · 进入主菜单 · 取得道具 · 到达关卡 · '
'退出关卡 · 存档/读档）· 出现时机是否阻塞 · 全屏还是弹窗 · 背景与边框 · '
'**字体族/字重/字距** · 排版 · 图标 · 颜色 · 闪烁 · **CRT 抖动 · 扫描线 · '
'噪点 · 静态** · 背景音乐/音效 · 是否朗读 · 持续帧数 · **最小观看时间** · '
'是否允许跳过 · Cancel 或 OK 的去向 · **连续重试上限** · 是否写日志 · 是否重启'
AP_DISC = '🔑 尤其要记"**多碟切换时插入哪一张 · 读盘重试几次 · '
'失败后提示原文**"，🔑 **是否明确区分空光驱 · 只读盘 · 错误盘 · 区域不匹配**'
AP_WEAR = '🔑 **CD/DVD 物理磨损也可能使原本合法的游戏无法使用** —— '
'🔴 **必须把"原版介质损耗"与"复制品差异"分开，'
'不能把光盘划痕产生的表现统一解释成 DRM**'
ANOM_RULE = '🔑 **故意错误内容是最容易被判成 bug 的 must-match。**'
ANOM_CASES = [
    ('某 RPG', '提升敌人生成率，并在接近最终 Boss 时删除存档、崩溃'),
    ('某惊悚作 1.05 后', '给角色加上**海盗眼罩**，并用**购买提示替换部分加载语**'),
    ('某音游 DS 版', '持续播放**偏离节拍的 vuvuzela** · 音乐质量变差 · 音符不加载'),
    ('某跑酷作', '某些边缘使玩家**近乎停止**，导致无法完成跳跃'),
    ('某射击作', '生成**速度更快且无法受伤的追踪敌人**，同时无法保存并随机崩溃'),
]
ANOM_MEAN = '🔑 复刻含义**不是模仿对介质的判定**，而是：'
'🔑 **如果原版某版本确实以可见异常著称，它就是该版本的预期表面**；'
'🔴 **重制若"修掉"，应另立旧版模式或保留可验证补丁，而不是悄悄抹平**'
CDKEY_RULE = '🔑 **CD-KEY 输入是字符消歧问题，不是任意字符串。**'
CDKEY_MAP = '🔑 官方帮助列出的视觉近似替换：数字 `0` 可尝试 `Q/D/O`；'
'数字 `1` 可尝试 `I/L`；字母 `O` 可尝试 `Q/D`；字母 `B` 可尝试 `8`；'
'字母 `G` 可尝试 `6`。🔑 **这说明正版用户也会在输入层失败**'
CDKEY_FIELDS = '分组长度 · **连字符是否自动插入** · 大小写是否等价 · '
'全角/半角 · **形似字符字形** · 光标跳格 · **粘贴后清洗规则** · '
'逐段校验还是提交后校验 · **输错多少位才开始反馈** · 失败是否清空前一段 · '
'是否显示最后一格遮罩 · 错误音 · 抖动 · 颜色 · 重试图标 · 键盘布局 · '
'**IME** · **读屏文案** · 帮助链接 · 客服电话 · 重试冷却'
CDKEY_NO = '🔑 **若原版不区分 `0/O` 或 `1/I`，复刻不应擅自加入严格校验**；'
'🔴 **若原版区分，也不能为"现代友好"自动纠错**'
ACT_FIELDS = '离线宽限次数 · 宽限时长 · 机器绑定是否转移 · 激活次数上限 · '
'同一账户已绑定错误 · 密钥已使用 · 区域不支持 · 时钟异常 · 证书失效 · '
'服务器不可达 · 维护页 · 客服电话 · 订单邮件要求 · 是否允许重试 · '
'失败后是否退回标题 · **是否允许继续离线游玩** · 失败后音频是否静音 · '
'**光驱门是否锁定**'
FALSE_POS = '🔑 **正版也可能被误报**：某系列在注册表缺少或序列号异常时，'
'🔑 **会在开局后摧毁玩家单位和建筑并自动判负**。'
'🔑 重制应**同时保留"原版已知误报表现"与"现代合法启动流程"，'
'🔴 **不要用一个无害弹窗覆盖历史版本的可见失败**'
REGION_RULE = '🔑 **区域与介质提示要逐版 · 逐地区 · 逐语言核对** —— '
'记"Insert Disc / 请将光盘插入驱动器 / 该区域不支持 / '
'This product is not available in your region / 区域不一致"等**原文**，'
'🔴 **而非翻译后的通用文案**；'
'并记国旗 · 语言名 · ISO 代码 · 区域锁定图标 · **选择地区的光标记忆** · '
'语言包是否仍加载 · 标题画面是否有区域标识 · **多碟换盘动画** · '
'包装与盘面的区域码 · 安装包语言与运行语言是否一致'
REGION_STATES = '🔑 状态机必须区分七类：**介质未找到 · 密钥失败 · '
'在线验证失败 · 账户已绑定 · 区域不匹配 · 维护 · 网络错误 · 未知错误**。'
'🔴 **否则复刻后所有失败都会退化成同一个现代化对话框，'
'原版的紧张感与玩家记忆同时消失**'

# 🔑 C Credits
CREDIT_RULE = '🔑 **Credits 不是文案页，而是版本化 · 可访问 · 可交互的证据链。**'
IGDA_RULE = '🔑 署名规范：**派生作品（port · remake · remaster · re-release）'
'必须把原始团队与新团队分列**，🔑 **原始团队在前**，'
'🔑 **两类选择同时可见**，并以"Original Team Credits"等类别标识；'
'🔑 **离职人员仍保留署名**；🔑 **任何有计费贡献者原则上都应被署名**'
MC_SAMPLE = '🔑 官方样本：按 Leadership · Design · Production · Visual Arts · '
'Quality Assessment · User Research 分组，'
'采用"**粗体组标题 + 职位 + 姓名**"的层级，'
'并单列"**Original Creator of Minecraft**"'
ORDER_RULE = '🔑 **排序语义必须按原版事实记录，不能按现代审美"整理"。**'
ORDER_WHY = '🔑 原版可能采用**部门权重 · 角色重要度 · 制作人指定 · 字母序 · '
'入职时间 · 拼音/罗马字 · 工会规范 · 历史遗留顺序**；'
'🔑 **"某人在最后"可能意味着末位分组 · 特别感谢 · 外包公司 · 外包个人 · '
'离职人员 · 别名 · 赞助支持者，也可能只是名单增长后没有重排**'
ORDER_EG = '🔑 案例：某作的 director 出现在最前，'
'而另一作东京团队把同一人物排在**字母序中的第 119 位**；'
'🔑 **调查数百款游戏后认为名单规则没有统一标准**'
ORDER_NO = '🔑 复刻的正确动作是记"**最后一位是谁 · 属于哪一组 · 前后是谁 · '
'该语言版本如何排序**"，🔴 **不得为了提高观感提前 · 归并 · '
'删除"公司宠物式"特别感谢**'
SCROLL_FIELDS = '进入触发（标题菜单/结局后/二周目/全部结局/失败退出）· '
'首次输入延迟 · **滚动像素/秒** · 加速后速度 · 匀速还是缓动 · 字号 · '
'字体族 · 字重 · 字宽 · 颜色 · 描边 · 阴影 · 背景 · 组标题间隔 · 人名行距 · '
'左右对齐 · 是否两端对齐 · 是否居中 · 最大可见行数 · 换行规则 · '
'长名处理 · 帧率 · 音乐与音效 · **音乐淡入淡出** · 最终一行离场动画 · '
'最后一屏停留时间 · 滚动完成后自动跳转位置'
SKIP_FIELDS = '🔑 跳过后：**何时刻可跳过 · 需长按/短按/双键/Start · '
'跳过后回到标题还是主菜单 · 是否算"已观看" · 是否有奖励 · '
'再次进入入口 · **不同语言是否共享进度**'
HIDDEN_RULE = '🔑 **隐藏内容不是彩蛋附录，而是 Credits 状态的后继节点。**'
HIDDEN_FIELDS = '是否可控制角色 · 是否可触发音效 · **名字是否可点击/悬停** · '
'点击后是否显示头像 · 语录 · 履历 · 招聘页 · 赞助链接 · 访问限制 · '
'是否出现第二段画面 · 额外动画 · **隐藏角色** · **开发者房间** · '
'Easter egg · 制作组照片 · 错误花絮 · 版本号 · **录制时间码** · '
'滚动结束后是否还有场景 · 是否返回标题 · **是否解锁菜单项** · '
'**是否生成存档标记**'
HIDDEN_COMBO = '🔑 若 Credits 后内容依赖**特定结局 · 达成率 · 难度 · 语言 · '
'控制器**，🔑 **应列为组合状态，而不是单独一个布尔值**'
THANKS_RULE = '🔑 **特别感谢与支持者名单是最容易发生"善意的破坏"的地方。**'
THANKS_FIELDS = 'Kickstarter/众筹支持者是否逐名列出 · 按金额还是随机 · '
'是否分组 · 姓氏是否公开 · **外语姓名是否罗马字化** · 字符是否缺失 · '
'**变音符号是否丢失 · 重音是否错误** · 全半角混用 · '
'**姓名顺序是否东西方反转** · 是否漏行 · 重复 · 被截断 · **被换行拆开**'
THANKS_NO = '🔑 **拼错不能简单"改正"**——应记原版错误码 · 截图 · 后续勘误屏。'
'🔴 **复刻不得为版式整齐删除支持者 · 合并重复名 · 用首字母替代全名，'
'也不能把众筹名单替换成公司名**'
THANKS_HALF = '🔑 报道指出"特别感谢"有时被用来收纳**已离职 · 贡献细节丢失 · '
'被视为次要**的人，因而被看作**半署名**'
EVOLVE_RULE = '🔑 **Credits 演化是补丁考古，不是美术微调。**'
EVOLVE_FIELDS = '`person_id` · `role_id` · `group_id` · `alias` · '
'**`order_index`** · `display_language` · `game_version` · `platform` · '
'`build_hash` · `evidence_url`'
EVOLVE_DIFF = '增员 · 删员 · 顺序变化 · 职务改名 · 部门重命名 · 拼写修正 · '
'语言新增 · 隐藏内容变化'
EVOLVE_NO = '🔑 **重制若把原作者从名单中移除，不是"品牌更新"，'
'🔴 **而是署名缺陷**；只有确有许可 · 合同或署名意愿变更证据时才可处理，'
'🔑 **并保留旧版快照**'
LOC_FIELDS = '每组标题的官方译法 · 角色名称的本地化 · **东亚姓名排序** · '
'日语假名/罗马字 · 繁简差异 · **阿拉伯语/希伯来语方向** · **泰语换行** · '
'德语长词压缩 · 法语空格规则 · 俄语字母 · 中文标点 · 全角数字 · '
'语言 fallback · 字体缺失替换 · 不同区域是否使用同一名单 · '
'**翻译组是否被列出** · 外包公司名是否本地化 · 版权符号与年份 · '
'**多语切换后是否保持滚动位置**'
LOC_NO = '🔑 若某语言版名单更短，🔑 **应标记为"删减 · 未完成还是暂代名单"，'
'🔴 **不应默认最新语言版最优**'

# 🔑 证据分级
VERIFY_5 = ['verified', 'secondhand', 'unverified', 'not_present']
VERIFY_RULE = '🔑 **"不可验证"要显式升级为字段值，而不是留空。**'
VERIFY_FIELDS = '`device_id` / `build_id` / `platform` / `region` / '
'`language` / `evidence_url` / `capture_device` / `timecode`'
VERIFY_NO = '🔑 **二手资料不能自动提升为 must-match**，'
'🔑 **但应保留状态骨架，避免复刻时把历史表面整段删除**'

CONFLICTS = [
    '❌ **把 Kiosk 当成零售版换一个标题画面**（忽略开机链路与运维仪式）',
    '❌ **超时立刻黑屏**（应"给出宽限—等待输入—超时清场"）',
    '❌ 把断电清零的高分误记成功能 / 把持久化的高分误记成每局重算',
    '❌ 把 Kiosk 版内容差异当零售版 bug 修掉',
    '❌ 把 Attract Sound 一概设为默认开 / 现代店铺机无音不当表现',
    '❌ **用无害的现代 DRM 弹窗覆盖历史版本的可见失败**',
    '❌ **悄悄"修掉"原版以可见异常著称的版本表面**（应另立旧版模式）',
    '❌ **擅自给 CD-KEY 加入严格校验或自动纠错**（0/O · 1/I · B/8 · G/6）',
    '❌ **把"请插入光盘"等介质动作统一解释成 DRM**',
    '❌ **按现代审美重排 Credits 顺序 · 归并 · 删除"公司宠物式"特别感谢**',
    '❌ **为版式整齐删除众筹支持者 · 合并重复名 · 用首字母替代全名**',
    '❌ **自动"改正"支持者姓名拼写**（应记错误码与勘误屏）',
    '❌ **把原作者从名单移除当"品牌更新"**（是署名缺陷）',
    '❌ **把单张滚动屏混排原始与新团队到难以辨认** / **把原版名单藏进菜单三层以下**',
    '❌ **默认最新语言版名单最优**（应标"删减/未完成/暂代"）',
    '❌ **任何规避 · 破解 · 密钥提取 · 模拟正版环境工具**（永久排除）',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（kiosk / timer / hw / variant / antip / anomaly / cdkey / '
               'region / credit / scroll / hidden / thanks / evolve）'),
    ('legacy_value', '**原版值**'),
    ('new_value', '新引擎值'),
    ('match', '**是否一致**'),
    ('verification', '**证据态**（verified/secondhand/unverified/not_present）'),
    ('evidence', '证据等级 1-8'),
]


def _hdr(t, w=80):
    print('=' * w)
    print(t)
    print('=' * w)


def cmd_kiosk(a):
    _hdr('🔑 试玩机（**不是零售版换皮**）')
    print(f'   {KIOSK_RULE}')
    print(f'\n主循环: {KIOSK_LOOP}')
    print(f'\n   {ANDROID_EG}')
    print(f'\n   {KIOSK_CLEAR}')
    print(f'\n   {ATTRACT_LOOP}')
    print(f'\n   {HISCORE_3}')
    print(f'\n   {VARIANT_RULE}')
    print(f'\n   {VARIANT_FIELDS}')
    print(f'\n   {EXPO_FIELDS}')
    return 0


def cmd_timer(a):
    _hdr('倒计时（**逐渐加压的中断流程**）')
    print(f'   {TIMER_RULE}')
    print(f'\n   {TIMER_FIELDS}')
    print(f'\n   {TIMER_MORE}')
    return 0


def cmd_hw(a):
    _hdr('硬件表面（**磨损反向定义体验**）')
    print(f'   {HW_RULE}')
    print(f'\n机柜: {HW_FIELDS}')
    print(f'\n控制面板: {HW_PANEL}')
    print(f'\n展会版: {HW_EXPO}')
    return 0


def cmd_variant(a):
    _hdr('Kiosk / 展会 / 评测版内容差异')
    print(f'   {VARIANT_RULE}')
    print(f'\n   {VARIANT_FIELDS}')
    print(f'\n   {EXPO_FIELDS}')
    return 0


def cmd_antip(a):
    _hdr('🔑 反盗版屏（**完整表现资产**）')
    print(f'   {AP_RULE}')
    print(f'\n   {AP_FIELDS}')
    print(f'\n   {AP_DISC}')
    print(f'\n   {AP_WEAR}')
    print(f'\n   {REGION_RULE}')
    print(f'\n   {REGION_STATES}')
    print(f'\n   {ACT_FIELDS}')
    print(f'\n   {FALSE_POS}')
    print('\n⚠️ **边界**：只记录可见表现，不记录任何检测实现或绕过方法')
    return 0


def cmd_anomaly(a):
    _hdr('🔑 故意错误内容（**最容易被判成 bug 的 must-match**）')
    print(f'   {ANOM_RULE}')
    print('\n公开案例:')
    for k, v in ANOM_CASES:
        print(f'   · {k}: {v}')
    print(f'\n   {ANOM_MEAN}')
    print('\n⚠️ **边界**：记录表现，不实现任何检测逻辑')
    return 0


def cmd_cdkey(a):
    _hdr('🔑 CD-KEY（**字符消歧问题**）')
    print(f'   {CDKEY_RULE}')
    print(f'\n   {CDKEY_MAP}')
    print(f'\n   {CDKEY_FIELDS}')
    print(f'\n   {CDKEY_NO}')
    print('\n⚠️ **边界**：不做密钥生成、不做在线验证绕过')
    return 0


def cmd_region(a):
    _hdr('区域与介质提示')
    print(f'   {REGION_RULE}')
    print(f'\n   {REGION_STATES}')
    return 0


def cmd_credit(a):
    _hdr('🔑 Credits（**版本化证据链**）')
    print(f'   {CREDIT_RULE}')
    print(f'\n   {IGDA_RULE}')
    print(f'\n   {MC_SAMPLE}')
    print(f'\n   {ORDER_RULE}')
    print(f'\n   {ORDER_WHY}')
    print(f'\n   {ORDER_EG}')
    print(f'\n   {ORDER_NO}')
    print(f'\n   {EVOLVE_RULE}')
    print(f'\n   {EVOLVE_FIELDS}')
    print(f'\n差异分类: {EVOLVE_DIFF}')
    print(f'\n   {EVOLVE_NO}')
    return 0


def cmd_scroll(a):
    _hdr('滚动（**精确时序**）')
    print(f'   {SCROLL_FIELDS}')
    print(f'\n   {SKIP_FIELDS}')
    print(f'\n本地化: {LOC_FIELDS}')
    print(f'\n   {LOC_NO}')
    return 0


def cmd_hidden(a):
    _hdr('隐藏内容（**Credits 状态的后继节点**）')
    print(f'   {HIDDEN_RULE}')
    print(f'\n   {HIDDEN_FIELDS}')
    print(f'\n   {HIDDEN_COMBO}')
    return 0


def cmd_thanks(a):
    _hdr('特别感谢与支持者（**善意的破坏**）')
    print(f'   {THANKS_RULE}')
    print(f'\n   {THANKS_FIELDS}')
    print(f'\n   {THANKS_HALF}')
    print(f'\n   {THANKS_NO}')
    return 0


def cmd_evolve(a):
    _hdr('Credits 演化（**补丁考古**）')
    print(f'   {EVOLVE_RULE}')
    print(f'\n   {EVOLVE_FIELDS}')
    print(f'\n差异分类: {EVOLVE_DIFF}')
    print(f'\n   {EVOLVE_NO}')
    print(f'\n   {IGDA_RULE}')
    return 0


def cmd_verify(a):
    _hdr('🔑 证据态（**不可验证要显式升级为字段值**）')
    print(f'   {VERIFY_RULE}')
    print(f'\n四态: ' + ' · '.join(VERIFY_5))
    print(f'\n字段: {VERIFY_FIELDS}')
    print(f'\n   {VERIFY_NO}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成边缘状态表: {a.init}')
    print('\n⚠️ 十三域：kiosk / timer / hw / variant / antip / anomaly / '
          'cdkey / region / credit / scroll / hidden / thanks / evolve')
    print('\n⚠️ `verification` 列＝**证据态**'
          '（verified/secondhand/unverified/not_present）')
    print('\n🔑 新模板：kiosk_states · coin_timer · hardware_wear · '
          'build_variants · anti_piracy · piracy_ingame_anomaly · '
          'cdkey_input · region_and_media · credits_structure · '
          'credits_presentation · credits_hidden_states · '
          'credits_special_thanks · credits_evolution · legacy_credits')
    print('\n🔑 新脚本：kiosk_recorder · credits_diff · cdkey_input_linter')
    print('\n⚠️ **边界**：三个脚本都只记录表面，'
          '不做密钥生成、不做绕过、不读受保护内存')
    return 0


def cmd_check(a):
    if not os.path.exists(a.check):
        print(f'❌ 文件不存在: {a.check}')
        return 2
    with open(a.check, encoding='utf-8', errors='replace', newline='') as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print('❌ 空表')
        return 1

    def g(r, k):
        return (r.get(k) or '').strip()

    mismatch, no_legacy, no_ver, no_grade = [], [], [], []
    for i, r in enumerate(rows, 1):
        m = g(r, 'match').lower()
        if m not in ('yes', 'y', 'true', '是', '一致'):
            mismatch.append(i)
        if not g(r, 'legacy_value') or g(r, 'legacy_value') == 'TODO':
            no_legacy.append(i)
        v = g(r, 'verification')
        if not v or v == 'TODO':
            no_ver.append(i)
        elif v not in VERIFY_5:
            no_ver.append(i)
        ev = g(r, 'evidence')
        if not ev or ev == 'TODO':
            no_grade.append(i)
        else:
            d = ev.split('.')[0].strip()
            if d.isdigit() and int(d) >= 7:
                no_grade.append(i)

    print('=' * 76)
    print(f'边缘状态层 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')
    if no_ver:
        print(f'\n🚫 {len(no_ver)} 条**证据态缺失或非法**'
              f'（行 {no_ver[:15]}）')
    if no_grade:
        print(f'\n🚫 {len(no_grade)} 条**证据等级缺失或 ≥7 级**'
              f'（行 {no_grade[:15]}）')

    if not (mismatch or no_legacy or no_ver or no_grade):
        print('\n✅ 边缘状态层：一致、原版值完整、证据态合法、证据达标')

    print('\n🔑 **试玩机不是零售版换皮；失败屏是完整表现资产；'
          'Credits 是版本化证据链。**')
    print('   🔑 **"不可验证"要显式升级为字段值，而不是留空。**')
    print('   🔴 **不得悄悄"修掉"原版以可见异常著称的版本表面。**')
    print('   ⚠️ **边界：不做规避 · 破解 · 密钥提取。**')
    return 1 if (a.gate_check and
                 (mismatch or no_legacy or no_ver or no_grade)) else 0


def main():
    ap = argparse.ArgumentParser(description='边缘状态层：Kiosk/反盗版/Credits')
    ap.add_argument('--kiosk', action='store_true')
    ap.add_argument('--timer', action='store_true')
    ap.add_argument('--hw', action='store_true')
    ap.add_argument('--variant', action='store_true')
    ap.add_argument('--antip', action='store_true')
    ap.add_argument('--anomaly', action='store_true')
    ap.add_argument('--cdkey', action='store_true')
    ap.add_argument('--region', action='store_true')
    ap.add_argument('--credit', action='store_true')
    ap.add_argument('--scroll', action='store_true')
    ap.add_argument('--hidden', action='store_true')
    ap.add_argument('--thanks', action='store_true')
    ap.add_argument('--evolve', action='store_true')
    ap.add_argument('--verify', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'kiosk': cmd_kiosk, 'timer': cmd_timer, 'hw': cmd_hw,
           'variant': cmd_variant, 'antip': cmd_antip,
           'anomaly': cmd_anomaly, 'cdkey': cmd_cdkey,
           'region': cmd_region, 'credit': cmd_credit,
           'scroll': cmd_scroll, 'hidden': cmd_hidden,
           'thanks': cmd_thanks, 'evolve': cmd_evolve,
           'verify': cmd_verify}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --kiosk / --timer / --hw / --variant / --antip / --anomaly / '
          '--cdkey / --region / --credit / --scroll / --hidden / --thanks / '
          '--evolve / --verify / --init / --check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
