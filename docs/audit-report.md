# 深度审计与修复报告（2026-09-28）

本报告记录一次自主深度审计的结构化结果：问题、根因、修复与验证状态。所有改动仅发生在
独立副本 `_repo-perf` 的分支上，未触碰 `_repo` 的 `main`。对专有协议与二进制只做只读检查，
未修改、打补丁或注入任何外部二进制与游戏程序。

## 1. 方法与证据标准

- 四条并行审计链路（子代理）：主线程卡顿与账号切换、协议与兼容性、并发-取消-代次与泄漏、
  边界与错误处理；另用 `gh` 核实上游事实。
- 每个修复先写能复现缺陷的公共行为测试并确认「改动前失败」，再改生产代码（红 → 绿）；
  必要时用 `git stash` 做改动前后 A/B。
- 性能结论统一用 `tools/quality/bench`（预热 + 多轮 + 中位/最小）产生，单次运行不作为依据。

## 2. 已修复项

| # | 问题 | 根因（证据） | 修复 | 回归测试 | 状态 |
| --- | --- | --- | --- | --- | --- |
| F1 | `core` 分片 1 无汇总输出且非 0 退出（`0xC0000409` 原生硬崩溃） | `tests/test_battle_report_analysis_load_service.py` 曾创建**非 GUI** 的 `QCoreApplication`；同进程后续 `test_role_catalog.py:38` 的 `QApplication.instance()` 直接返回它，控件在缺少 `QGuiApplication` 时被创建 → Qt 致命退出。最小复现：两模块同进程 | 新增 `tests/qt_application_fixture.py` 提供进程级唯一 GUI 应用；该测试改用它 | `tests/test_qt_application_isolation_boundaries.py`（2 条：禁止自建非 GUI 实例、同进程组合必须成功） | ✅ 已修 |
| F2 | 迁移产生外键违规后既无法回滚也被跳过 | `src/storage/sqlite/user_data_base.py` 原先在 `commit()` **之后**才 `PRAGMA foreign_key_check`，违规时事务已落库且 `schema_migration` 已写目标版本 | 校验移入事务内、提交之前 | `tests/test_user_data_migration_foreign_key_rollback.py`（红：`43 != 44`） | ✅ 已修 |
| F3 | 账号切换可能半途失败：账号索引已持久化但内存代次未推进 | `src/app/context.py` 的 stop/rebuild/notify/start 无逐项隔离；`stop()` 抛 `TimeoutError`（`inventory_sync_service.py:757-759`）会中断整条切换 | 新增 `_run_switch_step`，逐步隔离并记录告警 | `tests/test_app_context.py` 新增 3 条（停止失败、回调失败、重建失败） | ✅ 已修 |
| F4 | 过期扫描结果仍会搬移截图并删除临时目录 | `src/services/streaming_scan_service.py` 原先只在解析前与提交**后**复核代次，`commit()` 的副作用不可回退 | 提交前置复核，并抽出 `_is_stale_result` / `_stale_scan_stats` 去重 | `tests/test_streaming_scan_commit_boundaries.py`（红：`True is not false`） | ✅ 已修 |
| F5 | 评分与配装内核存在重复计算 | 角色级 `max_theoretical_weight` 在「装备 × 角色」内层重算；名称归一化每次重建别名字典；属性上下限搜索重复首轮且最多 256 轮重跑全量评分 | 角色级预计算 + 名称归一化缓存；搜索复用首轮结果并新增 `reuse_scores` | `tests/test_allocation_kernel_property_limits.py`（4 条，改动前 `1 != 2` 失败） | ✅ 已修 |
| F6 | 静态库短生命周期开连开销偏高 | 每次开连重复 `Path.resolve()`（Windows 走逐段 `GetFinalPathName`） | `_is_temp_path` 去二次解析并缓存 | `tests/test_static_storage_perf.py` | ✅ 已修 |
| F7 | 快照写入逐条 `execute` | 完整背包产生「装备数 + 词条数 + 角色数」次调用 | 分组 `executemany`（顺序与事务边界不变） | 既有快照测试 | ✅ 已修 |
| F8 | `static_game_data_dao.py` 878 行超 800 行硬限 | 单一文件承载过多查询 | 拆出 `static_game_data_character_growth_queries.py`（878 → 680 行） | `tests/test_repository_hygiene.py` | ✅ 已修 |
| F9 | 装备详情曲线按等级重复查询，且物品缺失时抛未处理的 `StopIteration` | `equipment_catalog_model.py` 原先每个等级各查一次曲线（53 属性 × 22 级 ≈ 1166 次），`next(...)` 无默认值 | DAO 新增 `evaluate_equipment_base_attribute_curve_levels`（一次读曲线、内存求值），`item_curves` 改为批量并返回空曲线 | `tests/test_static_catalog_equipment_page_ui.py` 新增 2 条（红：`StopIteration` + 读取次数 1166 ≠ 53） | ✅ 已修 |
| F10 | 「清空配装」逐条写库、失败后不刷新界面 | `equipment_display_controller.py` 原先循环调用单条 `deactivate_loadout_plan`，中途失败留下部分已生效状态且跳过缓存失效；并用 `getattr(..., lambda: [])` 掩盖缺失方法 | DAO 新增 `deactivate_loadout_plans`（校验后单事务批量写入）；控制器改用它，并在 `finally` 中统一失效缓存与刷新 | `tests/test_loadout_plan_batch_deactivate_dao.py`（3 条：非法输入整体回滚、批量去重生效、空批次无副作用） | ✅ 已修 |
| F12 | PR #64 新增的角色头像索引是死路径（`config/templates/roles` 在仓库与上游都不存在，恒返回空图） | `warehouse.py` 的 `_legacy_character_avatar` 依赖 `config/templates/roles`；实测对「早雾/灵可/零」全部返回空图；上游 API 查该目录返回 404 | 删除 `_role_avatar_index`、`_legacy_character_avatar` 及其回退调用；随之成为死代码的 `ROLE_AVATAR_ALIASES` / `normalize_role_avatar_name` 一并删除 | `tests/test_static_storage_perf.py`、`tests/test_warehouse_inventory.py` 中过时用例删除；`tests/test_static_storage_perf.py` 受影响 34 条测试通过 | ✅ 已修 |
| F11 | 账号切换/启动在 GUI 线程同步重建配装目录 **1174 ms** | `_load_data` 原先同步执行 `_read_allocation_catalog`，而同一份逻辑在 `_refresh_execute` 里包在 WorkerThread（线程模型不一致）；直接委托会因 `_refresh_execute` 在非 QWidget 宿主反向调用 `_load_data` 而无限递归 | 抽出 `_read_and_apply_allocation_catalog` 与 `_start_allocation_catalog_worker`；`_load_data` 对 GUI 宿主走 worker 并支持完成回调；`app.py` 的收尾（页面刷新、`account.switch_succeeded` 日志）移入 mixin 的 `_finish_account_switch`，由回调在目录就绪后执行，避免「完成日志早于数据就绪」 | `tests/test_main_window_catalog_load_boundaries.py`（2 条：非 GUI 宿主保持同步；GUI 宿主不得在调用线程读取——改动前断言失败） | ✅ 已修 |

## 3. 实测收益（`tools/quality/bench`）

| 场景 | 修复前 | 当前 | 说明 |
| --- | --- | --- | --- |
| 静态库开连（含一次查询） | 5.39 ms | **1.9 ms** | 第二次 `Path.resolve()` 与连接复用 |
| 评分整轮（700 件 × 8 角色） | 556 ms | **159 ms** | 角色级预计算 + 归一化缓存 |
| 属性上限排除搜索（每轮） | 403 ms | **19.5 ms** | 复用已评分结果 |
| 快照写入（600 件） | 209 ms | **185 ms** | `executemany` |
| 装备详情曲线（53 属性） | 144 ms | **16 ms** | 每条曲线只读一次（1166 → 53 次查询） |
| 配装目录重建：GUI 线程阻塞 | 1174 ms | **≈0 ms（转后台）** | 读取耗时本身不变，但不再阻塞界面 |
| 原生会话关闭的 GUI 线程等待（最坏） | ≈6 s | **≈2 s** | HUD 超时 2.0→0.5、快照域 1.5→0.4；实例不可用时跳过 |

## 4. 已定位但未修复项（含原因）

| # | 问题 | 证据 | 未修原因 |
| --- | --- | --- | --- |
| N1 | 正式库存指针可被「仅含本次变更 UID」的局部/按角色响应推进 | `src/services/warehouse_state_management.py:562-588`、`src/services/inventory_sync_service.py:572-597`；与 `begin_full_inventory_guard` 的全量冻结、稳定器注释（`inventory_snapshot_stabilizer.py:268-278`）冲突 | 严重度最高，但需改动同步状态机与稳定器交互，必须先有集成测试锁定「局部响应不得成为当前库存」，本轮时间不足以安全完成 |
| N2 | 轴分页缺 `complete` 字段时默认判为已完成 | `battle_axis_dao.py:249,264` 用 `get("complete", True)`；`nte_core_battle.py:590` `default=True`；而 `battle_axis_finalization_dao.py:127,156` 用 `default=False` | 缺上游/实机证据证明 Core 是否总是发送该字段；直接改默认值可能影响分页终止条件，需实机核对后再动 |
| N3 | 账号切换的 **主线程阻塞**已消除（F11），但目录重建本身仍是 1174 ms，只是搬到了后台线程 | 同 F11 | 后台读取仍需约 1.2 秒（一次重建 1414 条 SQL），期间执行页会短暂保持旧目录；若要缩短这段等待，需要处理 N4 的逐角色 N+1 |
| N4 | N+1 查询放大（剩余） | `legacy_allocation_static_catalog.py:183-245,250-280`（一次重建 1414 条 SQL 的主因）、`weighted_shell.py:201-208`、`configuration/controller.py:163-193` | 需新增批量 DAO 接口并逐个回归，属结构性改动；`equipment_catalog_model.py` 的部分已在 F9 修复 |
| N9 | 「清空配装」控制器路径缺少 Qt 层回归测试 | `equipment_display_controller.py` 的 `_clear_all_equipment` 依赖 `QMessageBox` | DAO 原子性已由 F10 的测试覆盖；控制器分支（失败提示、锁定跳过、`finally` 刷新）需 Qt 交互测试，本轮未补 |
| N5 | 静态库共享连接跨线程 `execute` 无锁保护；`close_shared_connections()` 生产无调用点 | `static_game_data_dao.py` `check_same_thread=False`，锁只保护字典 | 需先确定调用是否跨线程并设计连接池，避免以锁换死锁 |
| N6 | `ScanWorkerThread.run` 无 `finally` 释放 scanner；退出时主线程 `worker.wait(5000)`×3 | `src/app/workers.py:64-79`（对比 `:258-259` 有释放）、`scanning/controller.py:230-235` | 依赖真实 QThread 与 Qt 事件循环，无法用纯 Python 单测稳定复现 |
| N7 | 装备域完整性由背包域标志代替；能力不足时沿用遗留 ready 布尔 | `work_mode_runtime.py:710-716`、`native_inventory_lease.py:77-95,135` | 属工作模式与原生能力判定，需实机核对各域真实能力 |
| N8 | 角色头像索引路径为死路径 → **已在 F12 中删除** | 仓库与上游 `config/templates/roles` **均不存在**（上游 API 返回 404）；全仓无 `roles` 目录 → `_legacy_character_avatar` 恒返回空 | 见 F12：已按用户确认删除该路径（原顾虑是可由运行期模板根目录配置复活，用户判断该能力无实际使用者） |
| N10 | `warehouse.py` 的 `_template_root_candidates` / `_TEMPLATE_ROOTS` 在 F12 后成为只写不读的死访问器 | 头像路径删除后无人调用 | 保留：`configure_warehouse_view_template_roots` 是组合根 API（`app.py:147-153` 调用），简化或改名需要同时动 `app.py`，留待确认这是否算废弃入口 |

## 5. 验证结果

| 项目 | 结果 |
| --- | --- |
| `tools/quality/run_tests.py core -j 3` | **EXIT=0**，三分片 402/402/402 全部 `OK`（修复前分片 1 原生崩溃） |
| `tools/quality/run_tests.py full` | 3043 条，1 个 error：`test_static_data_manifest` 缺 `dist` 中的 OCR 模型（**既有环境问题**，还原源码后同样失败） |
| `ruff check src tools tests` | `All checks passed!` |
| `mypy` | 9 处既有报错，**无新增** |
| `python -m tools.quality.bench` | 四场景稳定输出，见第 3 节 |

## 6. 护栏与复核说明

- 所有改动限定在 `_repo-perf`；`_repo` 的 `main`、`deploy.ps1`、`deploy_to_program_files.bat` 未触碰。
- 未修改、打补丁或注入任何外部二进制、游戏程序或组件包；组件包相关结论均来自只读核对。
- `docs/roadmap.md` 中 0.1 原生完整性实机验收、0.3 抓包启动时序、0.4 Windows 验收仍未完成，
  本次未把它们当作缺陷，也未标记为已完成。
- 失败分类：F1–F8 为本次修复；FULL 的 `test_static_data_manifest` 为既有环境问题；
  其余既有噪声（Qt 平台插件、缺少游戏运行环境）未作为缺陷计入。
