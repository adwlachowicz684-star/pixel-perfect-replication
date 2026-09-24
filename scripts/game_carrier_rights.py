#!/usr/bin/env python3
"""输入载体 · UGC 创作链 · 数字权利账本 · 数据布局
（第三十九轮 A / B / C / D 类，含 E / F / G 补充）。

**🔑 本轮的视角**：
> 复刻的下一层漏洞**不在画面**，而在"**玩家如何伸手进去**"和
> "**数字权利如何流动**"。

本轮真正的缺口不是渲染或物理，而是复刻通常**默认继承**、却没有逐项记录的
**输入载体 · UGC 运行时契约 · 数字权利账本 · 数据布局语义**。

用法:
  game_carrier_rights.py --touch   # 🔑 **触控不是键盘映射**
  game_carrier_rights.py --gest   # 🔴 **手势必须竞争，不是分别回调**
  game_carrier_rights.py --stick  # 虚拟摇杆 · 掌机 · 陀螺仪
  game_carrier_rights.py --ugc    # 🔑 **官方编辑器是产品决策**
  game_carrier_rights.py --hot    # **热重载四档**
  game_carrier_rights.py --apiver # **API 三键兼容**
  game_carrier_rights.py --sand   # 🔑 **沙箱是能力交集**
  game_carrier_rights.py --conflict # 🔴 **禁止用目录扫描顺序冒充稳定**
  game_carrier_rights.py --shop   # 🔑 **权利可追溯 > 商店 UI 更现代**
  game_carrier_rights.py --pity   # **保底是可复刻的玩法状态**
  game_carrier_rights.py --refund # 🔴 **退款＝世界状态回滚预案**
  game_carrier_rights.py --layout # 🔑 **数据布局是可审计字段**
  game_carrier_rights.py --simd   # 🔴 **SIMD 与浮点重结合是高危区**
  game_carrier_rights.py --batch  # 批处理规则必须完整归档
  game_carrier_rights.py --dev    # 调试设施是**验证能力**
  game_carrier_rights.py --cloud  # 云串流＝**重构输入—反馈链**
  game_carrier_rights.py --g      # G 类五项新盲区
  game_carrier_rights.py --init ledger/carrier_rights.csv
  game_carrier_rights.py --check ledger/carrier_rights.csv --gate

退出码: 0 通过 / 1 缺项 / 2 用法错误
"""
import argparse
import csv
import os
import sys

# 🔑 触控
TOUCH_RULE = '🔑 **触控复刻的核心错误，是把屏幕输入降级成"哪个按键被按下"。**'
TOUCH_ITEMS = [
    '每个触点的**身份**（`pointerId` 或等价稳定标识）',
    '**面积 · 压力 · 坐标历史 · 时间顺序**',
    '**多个候选手势之间的竞争与锁定**',
    '**软键盘**与休眠恢复',
]
TOUCH_ZOOM = [
    '**第二根手指按下时由谁接管相机**',
    '缩放中心按**两指中点 / 主触点 / 内容锚点**计算？',
    '**一根手指抬起后如何继续拖动**',
    '**手指重新接触后是否恢复同一语义**',
]
TOUCH_WARN = '🔴 **按触点数组索引处理是高危做法** —— '
'不同平台和不同事件批次可能改变数组顺序；抬起后要保留短暂历史窗口'

# 🔴 手势竞争
GEST_RULE = '🔴 **滑动 · 长按 · 点击必须在同一状态机中竞争，'
'而不是分别写回调**'
GEST_THRESH = [
    '**落点容差**', '**滑动距离**', '**长按时间**', '**移动速度**',
]
GEST_ASK = [
    '候选手势**达到阈值前是否共享触点**',
    '**达到后是否独占**',
    '**失败后由谁接管**',
]
GEST_WARN = '🔴 **若三种手势都设为独立回调** → '
'同一根手指触发多次 · 取消消息不同步 · **动作顺序变化**'
GEST_SLOP = '🔑 touch slop ＝ 系统将手势判为**移动**前允许滑动的像素距离；'
'官方同时提供**历史位置 · 大小 · 时间 · 压力**，'
'并强调🔴 **手指触摸并不精确，判断往往依赖移动而非单次接触**'

# 摇杆/掌机/陀螺仪
STICK_ITEMS = [
    '**虚拟摇杆**：死区 · **跟随式 vs 固定式** · 可见性 · 边缘吸附 · 漂移',
    '**陀螺仪/加速度计**：采样率 · 滤波 · **漂移** · 校准 · 是否 must-match',
    '**掌机模式**（Switch / Steam Deck）：按键布局 · 屏幕尺寸 · 触控 · '
    '**休眠恢复**',
    '**触控反馈**：震动马达 · 音频反馈 · 视觉涟漪',
    '**误触与防抖**：手掌排斥 · 边缘忽略 · 多指冲突',
]
STICK_RULE = '🔑 键鼠手柄已覆盖，🔴 **但触控 / 掌机 / 陀螺仪几乎空白** —— '
'重制到移动端或掌机时必踩'

# 🔑 UGC
UGC_RULE = '🔑 **原版是否附带官方编辑器，应被记为项目级产品决策，'
'而不是开发便利性**'
UGC_KINDS = [
    '完整独立工具', '游戏内建造器', '数据表格', '脚本接口', '导出器',
]
UGC_FIELDS = [
    '工具名称 · 版本 · **可执行入口** · **项目格式**',
    '**是否必须随重制保留**',
    '创作者输出哪些文件',
    '**玩家运行时是否需要同一工具**',
]
UGC_WARN = '🔴 **若原版允许地图/脚本/动画/对话/配方/任务/UI 布局/着色器'
'被创作者修改，复刻版就不能只提供一个等价运行时** —— '
'否则社区只能依赖逆向格式和第三方注入'
UGC_TRADEOFF = '🔑 反方：官方编辑器会**暴露内部资产 · 增加维护成本 · '
'扩大攻击面**（多人反作弊或封闭平台尤甚）。'
'🔑 更稳妥：发布"**创作套件**"而非完整源码 —— '
'只导出稳定项目格式 · 模拟数据 · 文档 · 验证器，并保留**可禁用的导入沙箱**'
UGC_DECIDE = '🔴 **任何以"安全性"为由直接删除原版创作入口，'
'都必须进入产品与玩家影响评审**'

# 热重载
HOT_ONLY = [
    '**纯函数**', '**声明数据**', '材质参数', 'UI 布局', '关卡实体原型',
]
HOT_NEVER = [
    '**运行中实体**', '**单例状态**', '**已注册事件订阅**', '网络连接',
    '**原生资源句柄**', '**GPU pipeline**', '**已排程任务**', '**跨脚本引用**',
]
HOT_STEPS = [
    '保存影响域快照', '停止新任务', '卸载旧模块',
    '**保留命名版本的状态迁移函数**', '重放稳定事件或重声明世界',
    '**校验后置条件**', '**失败则回滚**',
]
HOT_TIERS = ['none', 'data_only', 'declarative', 'stateful_migration']
HOT_LUA = '🔴 Lua 类环境尤其应把 **package 缓存 · 全局表 · 定时器 · 回调**'
'作为显式资源，🔴 **不能依赖"重新 require 一遍"**'

# API 版本
APIVER_KEYS = [
    '`mod_api_version`', '模块级 `semver`', '对应 `game_version`',
    '最低/最高支持版本', '兼容层版本', '**废弃日期**',
]
APIVER_WHY = [
    '🔴 **仅比较游戏大版本**无法识别新增回调 · 参数重排 · 枚举改值 · '
    '**事件触发时机**',
    '🔴 **仅比较 semver** 无法处理引擎热修复',
]
APIVER_EACH = [
    '名称', '**参数顺序与类型**', '默认值', '**触发阶段**', '取消语义',
    '异常行为', '线程', '重入规则', '**废弃替代方案**',
]
APIVER_STAGE = ('🔑 加载顺序不只是"谁先注册"，'
               '还包括**并行初始化 · 跨模组消息 · 线程安全**')

# 沙箱
SAND_RULE = '🔑 **沙箱是能力交集，而不是把脚本放进独立进程就天然安全**'
SAND_CAPS = [
    '能力清单', '**资源配额**', '**CPU/指令/内存上限**',
    '**文件与网络白名单**', '**禁止或限制 `loadstring`**',
    '**脚本身份与签名**', '**日志和崩溃隔离**',
]
SAND_INTERSECT = '🔑 子容器能力由**祖先能力交集**决定；'
'服务端脚本默认不向客户端复制'
SAND_WARN = '🔴 **原生插件与脚本 VM 必须分开** —— '
'🔴 **允许加载任意动态库 ≠ 允许模组，而是允许第三方代码进入进程边界**'

# 冲突
CONFLICT_FIELDS = [
    '加载阶段', '静态依赖', '分组', '组内优先级',
    '**覆盖/合并/拒绝策略**', '**冲突诊断**',
]
CONFLICT_ORDER = [
    '**硬约束**（循环 · 缺失依赖 · 权限）',
    '**版本兼容**',
    '**显式负载组**',
    '**玩家固定顺序**',
    '**稳定排序**',
]
CONFLICT_MERGE = [
    '值覆盖', '列表追加', '映射键覆盖', '引用重写', '**脚本事件订阅**',
]
CONFLICT_THREE = ['changed（修改原记录）', 'added（新增记录）',
                  'known_difference（已知偏离）']
CONFLICT_RULE = '🔴 **禁止用"目录扫描顺序"冒充稳定性** —— '
'日志不仅要报告"某模组胜出"，还要列出**所有候选 · 键路径 · 版本 · 原因 · '
'受影响语义**'
CONFLICT_WORKSHOP = [
    '🔑 订阅 · 取消订阅 · 下载状态 · 优先级下载 · 安装状态 · 依赖 · 变更通知',
    '🔴 **订阅发生在游戏外** · **下载晚于启动** · '
    '**取消订阅只在退出后生效**',
    '🔑 每个订阅项应有 `published_file_id + item_version + content_hash + '
    'dependency_graph + entitlement`',
    '🔴 **不应把平台 ID 当作全局资产 ID**',
]

# 🔑 内购
SHOP_RULE = '🔑 **内购复刻的底线是"数字权利可以追溯"，'
'而不是把商店 UI 做得更现代**'
SHOP_TWO = [
    ('**真钱侧**', '平台 · 地区 · 税费 · 币种 · **价格档** · 含税价 · 支付状态'),
    ('**游戏内侧**', '不可交易软币 · 可交易代币 · 订阅期限 · DLC 权利 · '
     '**装饰性资产**'),
]
SHOP_KINDS = [
    '**消耗品**', '**非消耗品**', '**自动续订订阅**', '**非续订订阅**',
]
SHOP_ASK = [
    '是否可购买多次', '是否跨设备恢复', '**失败后是否自动补发**',
    '**退款后如何处理**', '**跨平台账号如何映射**',
]
SHOP_WARN = '🔑 软币**不能直接成为法定货币等价物**；'
'赠送 · 活动 · 订阅附赠 · 跨平台转移 · **测试币**必须标记来源'

PITY_ITEMS = [
    '**独立保底还是共享保底**',
    '计数键是**玩家 / 账号 / 池 / 服务器 / 活动**',
    '**计数是否随抽随写**',
    '**读取旧存档时如何处理**',
    '**版本迁移是否重置**',
    '跨平台是否合并 · 退款是否回滚 · 账号删除是否清除',
]
PITY_RULE = '🔑 **保底、概率与进度不是合规文本，而是可复刻的玩法状态**'
PITY_ATOMIC = '🔴 **保底计数器与服务端权利账本必须原子写入** —— '
'🔴 **绝不能只在客户端 `PlayerPrefs`、本地 JSON 或分析事件里保存**'
PITY_EMO = '🔑 若原版存在"**十连第九次后必定命中**"等情绪设计，'
'🔴 **计数器重置边界本身就是 must-match**，'
'重制版不能为提高可维护性把独立池合并成共享池'

# 收据
RECEIPT_FLOW = [
    '客户端获得**平台证明**',
    '服务端以 `originalTransactionId` / `orderId` / `purchaseToken` '
    '等**幂等键**校验',
    '**原子写入票据与权利**',
    '客户端以**幂等结果**完成消耗或确认',
    '**重试时只查询服务端账本**',
]
RECEIPT_STATES = [
    '支付进行中', '**票据验证中**', '已授予', '已消耗', '**已撤销**',
    '**争议中**',
]
RECEIPT_WARN = '🔴 **"玩家付款成功" ≠ "游戏已完成权利授予"** —— '
'🔴 **不能在收到平台回调时直接增加货币**'
RECEIPT_CONSUME = '🔑 商品在授权后需尽快确认：消耗品用 consume，'
'非消耗品用 acknowledge；🔴 **逾期未确认会被自动退款并撤销**'

# 🔴 退款
REFUND_RULE = '🔴 **退款处理必须从"扣钱"升级为"世界状态回滚预案"**'
REFUND_HARD = [
    '**已消耗金币**', '**已打开箱子**', '**已用于合成的货币**',
    '**已交易物品**', '**已分享给队友的掉落**', '**已改变剧情的道具**',
]
REFUND_STRATEGY = [
    ('未使用消耗品', '可撤销'),
    ('已使用消耗品', '可取消后续权利或**保留已结算结果**'),
    ('非消耗品', '可禁用'),
    ('订阅', '按平台策略到期或立即撤销'),
    ('赠予/交易', '**只撤销授予者权利**，或由服务端按规则拆分'),
]
REFUND_FIELDS = [
    '可撤销性', '撤销策略', '**撤销前快照**', '冲突处理',
    '`refund_reason`', '`platform_notification_id`', '`revoked_rights`',
    '`world_snapshot`', '**人工审核入口**',
]
REFUND_NOTE = '🔑 **平台通知只负责告知，不负责决定所有游戏内后果**'

OFFLINE_SHOP = [
    '离线商品目录**是否缓存**',
    '**票据是否本地排队**',
    '重试次数', '**最终失败文案**',
    '失败后是否仍允许离线游玩',
    '恢复网络后是否**先同步权利**',
    '断点续传是否使用**同一幂等键**',
]
OFFLINE_WARN = '🔴 **缓存只能保存目录展示与本地待确认票据，'
'不能保存"已经获得"的权利**'
PRICE_FIELDS = [
    '地区', '币种', '**税前/税后**', '展示价', '支付处理器费', '税率',
    '价格档位', '**整数价格约束**', '小数处理', '动态汇率策略', '测试区域',
]
PRICE_WARN = '🔑 **旧价格 · 涨价 · 折扣必须保留历史版本** —— '
'🔴 **同一账号跨区迁移时，不能让玩家通过切换区域重复获得差价补偿**'

# 🔑 数据布局
LAYOUT_RULE = '🔑 **数据布局不是实现细节，而是原游戏"如何遍历世界"的语义**'
LAYOUT_EXAMPLE = [
    'AoS：连续存储完整粒子，适合每次访问多个字段',
    'SoA：把 x[] y[] z[] life[] flag[] 分开，适合只处理寿命或位置的系统',
]
LAYOUT_FIELDS = [
    'AoS / SoA / **AoSoA** / 其他',
    '每个成员的**显式对齐**',
    '**热字段与冷字段是否分离**',
    '是否按 **64 字节缓存行**分块',
    '是否**消除伪共享**',
    '**分配 · 释放 · 重分配的触发条件**',
]
LAYOUT_CALC = '🔑 计算字段要从 **C++ `offsetof` · 反射 · 编译器断言**生成，'
'🔴 **禁止在文档里手工抄录**'
LAYOUT_ORDER = '🔴 **容器默认按插入顺序遍历的地方，'
'不能把 `std::unordered_*` · 字典 · 集合 · 并行任务当成"等价实现"**'
LAYOUT_ECS = '🔑 即便使用相同 ECS，🔴 **也不能由此推出实体顺序 · '
'事件顺序 · 模拟结果必然一致**'

SIMD_RISK = [
    '**自动向量化**', '**指令集差异**', '**融合乘加（FMA）**',
    '**聚合顺序**', '**冗余计算消除**', '**跨平台数学库**',
]
SIMD_RULE = '🔴 **SIMD 与浮点重结合是 must-match 的高危区**'
SIMD_STRATEGY = [
    '保留一个"**标量黄金路径**"',
    '**关闭不兼容的快速数学**',
    '**逐对象或逐系统比较哈希**',
    '🔑 **只有结果与参考一致时，才允许启用 SIMD / 多线程 / SoA 优化**',
]
SIMD_WARN = '🔴 **把 `-ffast-math` 视为性能开关会破坏核心信条** —— '
'这不是反对优化，而是要求**优化后重新验证**，'
'并通过**稳定排序或定点替代**控制不确定性'

BATCH_ITEMS = [
    '静态合批', '动态合批', '**GPU 实例化**', 'SRP Batcher 类机制',
    '**排序键**', '材质变体', '渲染队列', '光照模式', '阴影', '透明度',
    '排序层', '**距离排序**',
]
BATCH_RULE = '🔑 批处理规则必须**完整归档**；'
'🔴 **不能为降低 draw call 改变透明对象顺序**'
BATCH_RES = [
    '句柄生命周期', '依赖加载', '异步阶段', '内存预算', '**驻留峰值**',
    '释放延迟', '流式窗口', '后台驱逐',
]
BATCH_TEST = '🔑 压力测试以**低内存设备与长时游玩**为 must-pass，'
'🔴 **而不是只看平均帧率**'

# 调试
DEV_RULE = '🔑 **调试设施是复刻验证能力，而不是随手写的控制台**'
DEV_EACH = [
    '名称', '参数', '默认值', '**所属权限域**', '**是否修改存档**',
    '**是否影响随机**', '**是否可回滚**', '同步或异步', '结果如何返回',
    '失败如何提示',
]
DEV_STATES = [
    'development', 'debug_build', 'shipping_with_debug_menu',
    '**player_unlocked_cheat**', 'remote_tool', 'disabled',
]
DEV_WARN = '🔴 **不能用单一"开发版/发布版"开关代替**'
DEV_CONSOLE = [
    '打开控制台必须**禁用游戏快捷键与文本输入穿透**',
    '作弊码要保留**原输入序列 · 大小写 · 持续时间 · 菜单状态 · '
    '多人封禁语义**',
    '启动参数要记**解析顺序 · 重复键策略 · 未知参数处理 · '
    '签名或哈希校验 · 危险命令白名单 · 远程调用边界**',
]
DEV_PLAYER = '🔑 **"玩家可达调试功能"**：若原版把它作为彩蛋或速通策略，'
'🔴 **迁移后删除 · 重命名 · 改键均须评审**'
DEV_LOG = [
    '模块', '等级', '时间戳', '**帧号**', '**世界时钟**', '**实体 ID**',
    '原因', '上下文', '**脱敏策略**',
]

# 云串流
CLOUD_RULE = '🔑 **云串流不是"降低分辨率"，'
'而是重新构造整个输入—反馈链**'
CLOUD_CHAIN = [
    '采集', '编码', '传输', '**Jitter Buffer**', '解码', '渲染',
    '**音频相对视频偏移**', '**端到端动作响应**',
]
CLOUD_WARN = '🔑 重制前应建立**端到端测量**，🔴 **而不是只测网络 RTT**'
CLOUD_DIFF = [
    '按键重映射', '虚拟鼠标', '剪贴板', '文件选择', '软键盘',
    '**手柄热插拔**', 'HDR', '超宽屏', '摄像头', '麦克风', '蓝牙耳机',
    '**平台 overlay 与原生设备不一致**',
]
CLOUD_SAVE = '🔴 **存档不能在云端和本地各自写权威副本** —— '
'必须明确谁持有时钟与状态权威'
CLOUD_NO = [
    '🔴 **不能因带宽变化自动把必须同步的动作改成客户端预测**',
    '🔴 **不能因画质降级而删除原版输入反馈**',
    '🔑 动态码率/分辨率/帧率切换必须**映射为明确的游戏模式**，'
    '并保留原生设备的独立配置',
    '🔑 本地触觉和音频若无法穿透到云端，应**显示明确的离线/不可用状态**，'
    '🔴 **而不是静默把扳机或震动变成视觉提示**',
]

G_FIVE = [
    ('**游戏内浏览器 / WebView**',
     '记**域名白名单 · 协议 · Cookie · 存储 · 剪贴板 · 键盘监听 · 下载 · '
     'JavaScript 桥**；🔴 **登录页与游戏内网页应分进程或隔离上下文，'
     '禁止通用 WebView 任意注入**'),
    ('**屏幕阅读器与无障碍语义**',
     '🔴 **即使原版未完善，也不能删除原表达后只留纯文本**；'
     '应新增独立语义树，记**焦点顺序 · 角色 · 标签 · 值 · 状态变化通知 · '
     '可替代输入**'),
    ('**玩家创作物的授权 · 个人数据 · 资产哈希**',
     '记**作者身份 · 许可证 · 来源 URL · 衍生关系 · 第三方素材 · '
     '撤回权 · 删除流程**；🔴 **不能用"玩家上传"替代授权**'),
    ('**实时协作**（多人编辑 / 观战创作）',
     '记**操作所有权 · 光标 · 选区 · 撤销栈 · 断线重连 · 权限 · '
     'CRDT/OT 冲突决议**；🔴 **不能用"最后写入获胜"替代协作语义**'),
    ('**机器学习 / 数据驱动资产迁移**',
     '🔑 **模型权重 · 算子版本 · 量化 · 归一化 · 坐标系 · 帧率 · '
     '输入裁剪 · 随机种子 · 后处理**都可能改变行为。'
     '🔴 **迁移不能只测平均指标**，应在固定回放输入下比较'
     '**逐帧动作 · 置信度 · 触发次数 · 最终剧情分支**。'
     '若只是分析工具或格式转换器，应标 `tooling`，'
     '🔴 **不应默认进入运行时 must-match**'),
]

CONFLICTS = [
    '❌ **把触摸噪声当作按键事件**',
    '❌ **把三种手势做成独立回调**（同一手指触发多次）',
    '❌ **按触点数组索引处理**（平台会改顺序）',
    '❌ 用"**绝对顺序**"覆盖注册顺序',
    '❌ 允许脚本**任意热替换单例**',
    '❌ **客户端自行记账权利**（保底计数）',
    '❌ **把 `-ffast-math` 当性能开关**',
    '❌ **为降低 draw call 改变透明对象顺序**',
    '❌ **把自动批处理视为可自由切换的黑盒**',
    '❌ 把 `unordered_*` / 字典 / 集合当"等价实现"',
    '❌ **用"安全性"为由直接删除原版创作入口而不评审**',
    '❌ **把平台 ID 当全局资产 ID**',
    '❌ **保存"已经获得"的权利到离线缓存**',
    '❌ 用"**最后写入获胜**"替代协作语义',
    '❌ **静默把扳机或震动变成视觉提示**（云串流）',
]

FIELDS = [
    ('item_id', '项编号'),
    ('domain', '域（touch / gest / stick / ugc / hot / apiver / sand / '
               'conflict / shop / pity / refund / layout / simd / batch / '
               'dev / cloud / g）'),
    ('legacy_value', '**原版值**'),
    ('new_value', '新引擎值'),
    ('match', '**是否一致**'),
    ('tolerance', '**允许偏差**'),
    ('evidence', '证据等级 1-8'),
]


def _hdr(t, w=80):
    print('=' * w)
    print(t)
    print('=' * w)


def cmd_touch(a):
    _hdr('🔑 触控（**不是键盘映射**）')
    print(f'   {TOUCH_RULE}')
    print('\n必录:')
    for t in TOUCH_ITEMS:
        print(f'   · {t}')
    print('\n双指缩放四问:')
    for z in TOUCH_ZOOM:
        print(f'   · {z}')
    print(f'\n   {TOUCH_WARN}')
    return 0


def cmd_gest(a):
    _hdr('🔴 手势（**必须竞争**）')
    print(f'   {GEST_RULE}')
    print('\n四类阈值: ' + ' · '.join(GEST_THRESH))
    print('\n必答:')
    for g in GEST_ASK:
        print(f'   · {g}')
    print(f'\n   {GEST_WARN}')
    print(f'\n   {GEST_SLOP}')
    return 0


def cmd_stick(a):
    _hdr('虚拟摇杆 · 掌机 · 陀螺仪')
    for s in STICK_ITEMS:
        print(f'   · {s}')
    print(f'\n   {STICK_RULE}')
    return 0


def cmd_ugc(a):
    _hdr('🔑 UGC（**官方编辑器＝产品决策**）')
    print(f'   {UGC_RULE}')
    print('\n形态: ' + ' · '.join(UGC_KINDS))
    print('\n必录:')
    for f in UGC_FIELDS:
        print(f'   · {f}')
    print(f'\n   {UGC_WARN}')
    print(f'\n   {UGC_TRADEOFF}')
    print(f'\n   {UGC_DECIDE}')
    return 0


def cmd_hot(a):
    _hdr('热重载（**四档**）')
    print('可重载: ' + ' · '.join(HOT_ONLY))
    print('\n🔴 不应被任意替换: ' + ' · '.join(HOT_NEVER))
    print('\n流程: ' + ' → '.join(HOT_STEPS))
    print('\n分档: ' + ' · '.join(HOT_TIERS))
    print(f'\n   {HOT_LUA}')
    return 0


def cmd_apiver(a):
    _hdr('API 兼容（**三键**）')
    print('   ' + ' · '.join(APIVER_KEYS))
    print('\n为什么三键:')
    for w in APIVER_WHY:
        print(f'   {w}')
    print('\n每个 API 至少登记: ' + ' · '.join(APIVER_EACH))
    print(f'\n   {APIVER_STAGE}')
    return 0


def cmd_sand(a):
    _hdr('🔑 沙箱（**能力交集**）')
    print(f'   {SAND_RULE}')
    print('\n能力项: ' + ' · '.join(SAND_CAPS))
    print(f'\n   {SAND_INTERSECT}')
    print(f'\n   {SAND_WARN}')
    return 0


def cmd_conflict(a):
    _hdr('🔴 加载冲突（**禁止目录扫描顺序**）')
    print('必录: ' + ' · '.join(CONFLICT_FIELDS))
    print('\n仲裁顺序:')
    for i, c in enumerate(CONFLICT_ORDER, 1):
        print(f'   {i}. {c}')
    print('\n合并方式: ' + ' · '.join(CONFLICT_MERGE))
    print('\n同名三态: ' + ' · '.join(CONFLICT_THREE))
    print(f'\n   {CONFLICT_RULE}')
    print('\n创意工坊:')
    for w in CONFLICT_WORKSHOP:
        print(f'   · {w}')
    return 0


def cmd_shop(a):
    _hdr('🔑 内购（**权利可追溯**）')
    print(f'   {SHOP_RULE}')
    print('\n两条账:')
    for k, v in SHOP_TWO:
        print(f'   {k:<14} {v}')
    print('\n品类: ' + ' · '.join(SHOP_KINDS))
    print('\n每类必答: ' + ' · '.join(SHOP_ASK))
    print(f'\n   {SHOP_WARN}')
    print('\n收据流程:')
    for i, r in enumerate(RECEIPT_FLOW, 1):
        print(f'   {i}. {r}')
    print('\n状态机: ' + ' · '.join(RECEIPT_STATES))
    print(f'\n   {RECEIPT_WARN}')
    print(f'\n   {RECEIPT_CONSUME}')
    return 0


def cmd_pity(a):
    _hdr('保底（**可复刻的玩法状态**）')
    for p in PITY_ITEMS:
        print(f'   · {p}')
    print(f'\n   {PITY_RULE}')
    print(f'\n   {PITY_ATOMIC}')
    print(f'\n   {PITY_EMO}')
    return 0


def cmd_refund(a):
    _hdr('🔴 退款（**世界状态回滚预案**）')
    print(f'   {REFUND_RULE}')
    print('\n难回滚项: ' + ' · '.join(REFUND_HARD))
    print('\n策略:')
    for k, v in REFUND_STRATEGY:
        print(f'   {k:<16} {v}')
    print('\n字段: ' + ' · '.join(REFUND_FIELDS))
    print(f'\n   {REFUND_NOTE}')
    print('\n离线:')
    for o in OFFLINE_SHOP:
        print(f'   · {o}')
    print(f'\n   {OFFLINE_WARN}')
    print('\n价格字段: ' + ' · '.join(PRICE_FIELDS))
    print(f'\n   {PRICE_WARN}')
    return 0


def cmd_layout(a):
    _hdr('🔑 数据布局（**可审计字段**）')
    print(f'   {LAYOUT_RULE}')
    print('\n布局:')
    for l in LAYOUT_EXAMPLE:
        print(f'   · {l}')
    print('\n必录: ' + ' · '.join(LAYOUT_FIELDS))
    print(f'\n   {LAYOUT_CALC}')
    print(f'\n   {LAYOUT_ORDER}')
    print(f'\n   {LAYOUT_ECS}')
    print('\n资源: ' + ' · '.join(BATCH_RES))
    print(f'\n   {BATCH_TEST}')
    return 0


def cmd_simd(a):
    _hdr('🔴 SIMD（**浮点高危区**）')
    print('风险: ' + ' · '.join(SIMD_RISK))
    print(f'\n   {SIMD_RULE}')
    print('\n策略:')
    for s in SIMD_STRATEGY:
        print(f'   · {s}')
    print(f'\n   {SIMD_WARN}')
    return 0


def cmd_batch(a):
    _hdr('批处理（**必须完整归档**）')
    print('   ' + ' · '.join(BATCH_ITEMS))
    print(f'\n   {BATCH_RULE}')
    return 0


def cmd_dev(a):
    _hdr('调试设施（**验证能力**）')
    print(f'   {DEV_RULE}')
    print('\n每个命令: ' + ' · '.join(DEV_EACH))
    print('\n状态: ' + ' · '.join(DEV_STATES))
    print(f'\n   {DEV_WARN}')
    print('\n控制台:')
    for d in DEV_CONSOLE:
        print(f'   · {d}')
    print(f'\n   {DEV_PLAYER}')
    print('\n日志字段: ' + ' · '.join(DEV_LOG))
    return 0


def cmd_cloud(a):
    _hdr('云串流（**重构输入—反馈链**）')
    print(f'   {CLOUD_RULE}')
    print('\n链路: ' + ' → '.join(CLOUD_CHAIN))
    print(f'\n   {CLOUD_WARN}')
    print('\n与原生不一致处: ' + ' · '.join(CLOUD_DIFF))
    print(f'\n   {CLOUD_SAVE}')
    print('\n禁止:')
    for c in CLOUD_NO:
        print(f'   {c}')
    return 0


def cmd_g(a):
    _hdr('G 类（**五项新盲区**）')
    for k, why in G_FIVE:
        print(f'\n   【{k}】\n      {why}')
    return 0


def cmd_init(a):
    os.makedirs(os.path.dirname(a.init) or '.', exist_ok=True)
    with open(a.init, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow([k for k, _ in FIELDS])
        w.writerow(['TODO'] * len(FIELDS))
    print(f'已生成载体/权利表: {a.init}')
    print('\n⚠️ 十七域：touch / gest / stick / ugc / hot / apiver / sand / '
          'conflict / shop / pity / refund / layout / simd / batch / dev / '
          'cloud / g')
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

    mismatch, no_legacy, no_tol, no_grade = [], [], [], []
    for i, r in enumerate(rows, 1):
        m = g(r, 'match').lower()
        if m not in ('yes', 'y', 'true', '是', '一致'):
            mismatch.append(i)
        if not g(r, 'legacy_value') or g(r, 'legacy_value') == 'TODO':
            no_legacy.append(i)
        if not g(r, 'tolerance') or g(r, 'tolerance') == 'TODO':
            no_tol.append(i)
        ev = g(r, 'evidence')
        if not ev or ev == 'TODO':
            no_grade.append(i)
        else:
            d = ev.split('.')[0].strip()
            if d.isdigit() and int(d) >= 7:
                no_grade.append(i)

    print('=' * 76)
    print(f'载体/权利 · {len(rows)} 条')
    print('=' * 76)
    if mismatch:
        print(f'\n🚫 **不一致** {len(mismatch)} 条（行 {mismatch[:15]}）')
    if no_legacy:
        print(f'\n❌ {len(no_legacy)} 条缺**原版值**（行 {no_legacy[:15]}）')
    if no_tol:
        print(f'\n🚫 {len(no_tol)} 条缺**允许偏差**（行 {no_tol[:15]}）')
    if no_grade:
        print(f'\n🚫 {len(no_grade)} 条**证据等级缺失或 ≥7 级**'
              f'（行 {no_grade[:15]}）')

    if not (mismatch or no_legacy or no_tol or no_grade):
        print('\n✅ 载体/权利：一致、原版值完整、偏差已声明、证据达标')

    print('\n🔑 **复刻的下一层漏洞不在画面，'
          '而在「玩家如何伸手进去」和「数字权利如何流动」。**')
    print('   **保底计数器必须原子写入服务端；绝不能只在客户端保存。**')
    print('   **把 -ffast-math 当性能开关会破坏核心信条。**')
    return 1 if (a.gate_check and
                 (mismatch or no_legacy or no_tol or no_grade)) else 0


def main():
    ap = argparse.ArgumentParser(description='输入载体与数字权利')
    ap.add_argument('--touch', action='store_true')
    ap.add_argument('--gest', action='store_true')
    ap.add_argument('--stick', action='store_true')
    ap.add_argument('--ugc', action='store_true')
    ap.add_argument('--hot', action='store_true')
    ap.add_argument('--apiver', action='store_true')
    ap.add_argument('--sand', action='store_true')
    ap.add_argument('--conflict', action='store_true')
    ap.add_argument('--shop', action='store_true')
    ap.add_argument('--pity', action='store_true')
    ap.add_argument('--refund', action='store_true')
    ap.add_argument('--layout', action='store_true')
    ap.add_argument('--simd', action='store_true')
    ap.add_argument('--batch', action='store_true')
    ap.add_argument('--dev', action='store_true')
    ap.add_argument('--cloud', action='store_true')
    ap.add_argument('--g', action='store_true')
    ap.add_argument('--init')
    ap.add_argument('--check')
    ap.add_argument('--gate-check', action='store_true')
    a = ap.parse_args()
    fns = {'touch': cmd_touch, 'gest': cmd_gest, 'stick': cmd_stick,
           'ugc': cmd_ugc, 'hot': cmd_hot, 'apiver': cmd_apiver,
           'sand': cmd_sand, 'conflict': cmd_conflict, 'shop': cmd_shop,
           'pity': cmd_pity, 'refund': cmd_refund, 'layout': cmd_layout,
           'simd': cmd_simd, 'batch': cmd_batch, 'dev': cmd_dev,
           'cloud': cmd_cloud, 'g': cmd_g}
    for k, fn in fns.items():
        if getattr(a, k):
            return fn(a)
    if a.init:
        return cmd_init(a)
    if a.check:
        return cmd_check(a)
    print('❌ 需要 --touch / --gest / --stick / --ugc / --hot / --apiver / '
          '--sand / --conflict / --shop / --pity / --refund / --layout / '
          '--simd / --batch / --dev / --cloud / --g / --init / --check 之一')
    return 2


if __name__ == '__main__':
    sys.exit(main())
