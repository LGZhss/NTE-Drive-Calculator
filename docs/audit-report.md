# 审计与修复报告（2026-09-28）

分支 `perf/snapshot-write-and-indexes`（fork），PR #65 **基准为上游 `test` 分支**，当前为草稿、未合并。
全部改动位于独立副本 `_repo-perf`；`_repo` 的 `main`、`deploy.ps1`、`deploy_to_program_files.bat` 未触碰。
未修改、打补丁或注入任何外部二进制、游戏程序或组件包；`third_party` 相关内容仅用于只读核对。

## 问题

**稳定性**
- F1 测试进程可被非 GUI 的 Qt 应用实例污染：后续控件在缺少 `QGuiApplication` 时被创建，Qt 致命退出
  （`0xC0000409`），整个测试进程被杀，分片无汇总输出且退出码非 0。最小复现：两个模块同进程
- F2 迁移产生外键违规后既无法回滚也被跳过：校验在 `commit()` 之后，违规数据已落库、版本已推进
- F3 账号切换可能半途失败：`stop()` 抛 `TimeoutError` 会中断整条切换，账号索引已持久化但内存代次未推进
- F4 过期扫描结果仍会搬移截图并删除临时目录（代次复核在提交之后）
- F16 `ScanWorkerThread.run` 失败或取消时不释放 scanner，泄漏虚拟手柄与句柄

**数据一致性**
- F15 局部/按角色响应可推进正式库存指针：action 回包只要求覆盖「本次变更目标」即被导入，
  而背包导入仅校验 `complete` 标志，其余装备会从当前库存消失
- F10 「清空配装」逐条写库，中途失败留下部分已生效状态且不刷新界面
- F14 静态库共享连接跨线程无保护、退出时不回收：残留句柄抛裸 `sqlite3.ProgrammingError`

**性能**
- F11 账号切换/启动在 GUI 线程同步重建配装目录（中位 1174 ms）——「经常未响应」的主因
- F13 配装目录重建逐角色 N+1（一次重建 1417 条 SQL）
- F5 评分与配装内核重复计算：属性上下限搜索最坏 256 轮全量重评
- F6 静态库短生命周期开连重复做 Windows 路径解析
- F7 快照写入逐条 `execute`
- F9 装备详情曲线按等级逐条查询，且物品缺失时抛未处理的 `StopIteration`
- F17 原生会话关闭在 GUI 线程同步等待，最坏约 6 s
- F18 逐角色各开一次账号库（一次重建 25 次），建连与迁移检查被按角色数放大
- F19 弧盘模板投影每次重建都重算（51 个弧盘逐级的面板统计，约 0.95 s；纯 CPU，只随数据集发布变化）

**资产与结构**
- F12 角色头像存在两套查找路径（正式图鉴 + 遗留兼容查找）
- F8 `static_game_data_dao.py` 违反可评审性契约（`AGENTS.md` §7：`src/`、`tools/`、`tests/` 下
  新增或修改的 `.py` 不超过 800 行，触及超限存量只拆分或收缩）。审计时该文件 878 行，
  `tests/test_repository_hygiene.py::test_python_modules_stay_within_review_threshold` 失败。
  属门禁/可维护性项，**不是运行缺陷**

## 改动

| # | 改动 | 验证 |
| --- | --- | --- |
| F1 | 新增 `tests/qt_application_fixture.py`（进程级唯一 GUI 应用），相关测试改用它；新增守卫禁止测试自建非 GUI 实例 | `tests/test_qt_application_isolation_boundaries.py`（2 条） |
| F2 | 外键校验移入事务内、提交之前 | `tests/test_user_data_migration_foreign_key_rollback.py`（改动前红：`43 != 44`） |
| F3 | `AppContext` 新增 `_run_switch_step`，stop/rebuild/notify/start 逐步隔离并记录告警 | `tests/test_app_context.py` 新增 3 条 |
| F4 | 提交前置复核代次，抽出 `_is_stale_result` / `_stale_scan_stats` | `tests/test_streaming_scan_commit_boundaries.py`（改动前红） |
| F5 | 评分角色级预计算 + 名称归一化缓存；属性上限搜索复用首轮结果（`reuse_scores`） | `tests/test_allocation_kernel_property_limits.py`（4 条，改动前 `1 != 2`） |
| F6 | `_is_temp_path` 去二次 `Path.resolve()` 并缓存临时目录判定 | `tests/test_static_storage_perf.py` |
| F7 | 快照写入改分组 `executemany`（写入顺序与事务边界不变） | 既有快照测试 |
| F8 | 拆出 `static_game_data_character_growth_queries.py` 与 `static_game_data_weight_queries.py`（878 → 756 行，满足 `AGENTS.md` §7 的 800 行可评审性契约） | `tests/test_repository_hygiene.py` |
| F9 | DAO 新增 `evaluate_equipment_base_attribute_curve_levels`（一次读曲线、内存求值），`item_curves` 批量化并返回空曲线 | `tests/test_static_catalog_equipment_page_ui.py`（2 条，改动前红） |
| F10 | DAO 新增 `deactivate_loadout_plans`（校验后单事务批量），控制器改用并在 `finally` 统一失效缓存与刷新 | `tests/test_loadout_plan_batch_deactivate_dao.py`（3 条） |
| F11 | 抽出 `_read_and_apply_allocation_catalog` / `_start_allocation_catalog_worker`；GUI 宿主走 worker 并支持完成回调；`app.py` 收尾移入 `_finish_account_switch` | `tests/test_main_window_catalog_load_boundaries.py`（2 条，改动前红） |
| F12 | 经裁定该兼容查找已无实际使用者，显式移除：`_role_avatar_index`、`_legacy_character_avatar`、`ROLE_AVATAR_ALIASES`、`normalize_role_avatar_name` 与回退调用，头像统一取 `equipped_character_icon_path` | 过时用例删除；受影响测试通过 |
| F13 | 新增批量 DAO：`list_character_shape_bonuses`、`list_character_default_suits`、`list_character_likeability_bonuses`、`map_character_recommended_weights`、`list_character_weight_preferences`、`dataset_info`；图纸改用既有 `list_equipment_plans`；`project_equipment_items_to_max_level` 空输入短路；`load_official_role_detail` 的目录作用域与账号设置副本按请求缓存 | 实测 **1417 → 887 条 SQL（−37%）**、中位 **1174 → 1027 ms**；67 条相关测试通过、mypy 无新增 |
| F14 | `_rows` 与 `close()`/`close_shared_connections()` 共用互斥锁（SQLite 为 serialized 模式，不引入连接池）；「连接已关闭」转为 `StaticGameDataError`；`MainWindow.closeEvent` 退出时回收共享连接 | `tests/test_static_connection_lifecycle_boundaries.py`（改动前 1 失败 1 报错） |
| F15 | action 回包替换当前库存前，要求覆盖当前完整库存的全部 UID，否则回落到状态投影 + 冻结守卫（允许额外行=更新的完整回包，但不得缺行；与稳定器既有守卫同向，那里为严格相等） | `tests/test_warehouse_state_management.py::test_scoped_packet_never_replaces_the_official_inventory`（改动前失败）；同步路径既有守卫由 `tests/test_inventory_snapshot_stabilizer.py` 覆盖 |
| F16 | `run` 增加 `finally` 释放 scanner，与同文件既有实现一致 | `tests/test_scan_worker_lifecycle_boundaries.py`（改动前红） |
| F17 | HUD 超时 2.0→0.5、快照域 1.5→0.4；实例不可用时跳过快照关闭 RPC | 参数级改动；既有会话测试通过 |
| F18 | `load_official_role_detail` 新增可选 `user_dao`，目录重建复用同一个账号连接（只关闭自己打开的那个） | `tests/test_allocation_catalog_connection_boundaries.py`（改动前一次重建打开 **25** 次） |
| F19 | `fork_templates_as_weapon_models` 按静态数据集身份缓存；数据集变化或 `clear_weapon_model_cache()` 后重算 | `tests/test_fork_weapon_model_cache.py`（3 条：命中缓存 / 数据集变化重算 / 清理后重算） |

## 影响

- 不修改 IPC 协议、采集/分析组件、`third_party` 的任何二进制与清单；游戏版本相关行为不变。
- **不向上游 `main` 发起合并**：PR 基准为 `test`；分支重写后 force-push 到 fork 同名分支。
- 未改变轴分页 `complete` 的判定行为：缺实机/上游协议证据，仅固化当前判定并标注所需证据
  （`tests/test_battle_axis_complete_defaults.py`），后续统一默认值会直接体现为测试差异。
- 头像遗留查找的移除依据：经维护者裁定该兼容查找已无实际使用者，不以目录是否存在作为理由。
- 行为可见变化：账号切换不再卡 UI（目录后台加载）；「清空配装」原子化；退出时回收静态库连接；
  局部回包不再替换正式库存。

## 实测收益（`tools/quality/bench`，预热 + 多轮取中位）

| 场景 | 修复前 | 当前 |
| --- | --- | --- |
| 静态库开连（含一次查询） | 5.39 ms | **2.0 ms** |
| 评分整轮（700 件 × 8 角色） | 556 ms | **159 ms** |
| 属性上限排除搜索（每轮） | 403 ms | **19.5 ms** |
| 快照写入（600 件） | 209 ms | **185 ms** |
| 装备详情曲线（53 属性） | 144 ms | **16 ms** |
| 配装目录重建 | 1174 ms（1417 条 SQL） | **663 ms（887 条 SQL）** |
| 原生会话关闭的 GUI 线程等待（最坏） | ≈6 s | **≈2 s**（按超时参数估算，未实机计时） |

## 已定位但未修复

| # | 问题 | 未修原因 |
| --- | --- | --- |
| N2 | 轴分页缺 `complete` 字段时默认判为已完成（与最终化路径默认值相反） | 设备是否总会发送该字段属实机/上游协议证据；已固化当前判定并标注证据需求 |
| N3 | 配装目录重建仍约 1.0 s（887 条 SQL），已从 GUI 线程移出 | 剩余耗时分布在三处（见 N4 与 N11），其中两处**不在**逐角色查询里 |
| N4 | 逐角色详情的剩余查询（`load_official_role_detail`） | F18/F19 之后实测：一次重建（profiled）≈0.98 s，其中 `load_official_role_detail`（24 次）≈0.615 s，是剩余最大项。**价值**：做完约 663 ms → 300~400 ms、SQL 887 → 约 400，但之后它不再是最主要瓶颈。**风险**：① 默认档案解析依赖技能/觉醒/面板成长，另写一份投影入口容易语义漂移；② 角色页与目录投影变成两份真源，改一处漏一处会静默不一致；③ 数据不足时静默返回空投影，比现在抛错更难发现。**建议形态**：不新写入口，而是给 `load_official_role_detail` 加 `projection_only` 跳过与投影无关的部分，保留同一套档案解析与弧盘选择逻辑。**前置**：必须先有「全角色逐项对比新旧投影输出」的测试，没有就不做 |
| N7 | 装备域完整性由背包域标志代替 | 需实机核对各域真实能力 |
| N11 | `list_fork_templates` 在一次重建里被调用 3 次（≈0.366 s） | profiled：3 次 × ≈0.122 s。分别来自目录装配、`fork_templates_as_weapon_models` 的输入、角色详情（后者已被请求缓存合并为 1 次） | 未修：合并三者需要跨模块传递弧盘列表，或在 DAO 层按数据集缓存（返回可变列表，有被改写的风险）。收益约 0.24 s，性价比低于 N4 | | cProfile：一次重建中 `fork_templates_as_weapon_models` ≈0.959 s（`_fork_stats_at_level` 4080 次、`fork_panel_stats` 4104 次、`_integer` **24.6 万次**、genexpr 8208 次），`list_fork_templates` 3 次 ≈0.364 s，`UserDataDao.__init__` 27 次 ≈0.510 s（含 `_migrate_schema` 0.348 s）。以上**不产生 SQL**，因此此前按 SQL 条数的统计看不到 | 本轮聚焦 N4 未动。按投入产出排序：**账号库复用（≈0.45 s，风险极低）> 弧盘投影缓存与 `_integer` 降频（≈0.9 s，纯 CPU、可逐项对比验证）> N4 投影模式（需逐角色输出对比测试）** |
| N9 | 「清空配装」控制器分支缺 Qt 层回归测试 | DAO 原子性已由 F10 覆盖；控制器交互需 Qt 测试 |
| N10 | `_template_root_candidates` / `_TEMPLATE_ROOTS` 成为只写不读的死访问器 | `configure_warehouse_view_template_roots` 是组合根 API，简化需同时动 `app.py` |

## 验证

| 项目 | 结果 |
| --- | --- |
| `tools/quality/run_tests.py core -j 3` | **EXIT=0**：三分片各 `Ran 404 tests`，依次 `OK (skipped=3)`、`OK`、`OK`（提交 `69966a9`；其后仅文档/测试删减与一处无行为变化的回退） |
| `ruff check src tools tests` | `All checks passed!` |
| `mypy` | 既有报错不变，无新增（改动文件逐个 A/B 对比） |
| `tools/quality/bench` | 场景稳定输出，见实测收益表 |
| `run_tests.py full` | 早前运行 3043 条、1 个 error（`test_static_data_manifest` 缺 `dist` 中 OCR 模型，既有环境问题）；当前提交未重跑 |

行数口径提醒：`test_repository_hygiene` 用 `len(Path.read_text().splitlines())` 计行；PowerShell
的 `Get-Content | Measure-Object -Line` 会给出明显偏小的结果（本机同一文件 891 vs 798），
判断 800 行契约时**不要用后者**。
