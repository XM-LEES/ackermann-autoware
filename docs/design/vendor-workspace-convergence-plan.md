# Vendor Workspace Convergence Plan

> 本文是后续实施的唯一执行计划。执行者不需要了解此前对话，但必须逐项满足本文的边界、门禁和验收条件。

## 1. 目标

在本次工作不继续修改 `src/core/`、不改变已经由 CarMaker 验证的 Hooke 产品行为、暂不使用 Orin 的前提下，重新整理第三方 ROS 依赖管理：

1. 保留 pilot 基线已经验证过的 Hooke 依赖集合和默认命令行为；
2. 让 Hooke 与 RC 使用同一套依赖解析、导入、补丁、构建和环境叠加机制；
3. 仅把“依赖选择结果、平台硬件依赖和工作区路径”作为平台差异；
4. RC 依赖集合必须从产品直接依赖和上游包依赖图推导、审查并锁定，不能继续把“82 包”当作设计前提；
5. 第三方源码、构建产物和安装产物继续作为可再生工作区，不纳入产品 Git 历史；
6. 只有本机验证与 CarMaker Hooke 回归都通过后，才允许进入 Orin 实机阶段。

## 2. 当前事实与问题

### 2.1 基线

- 产品仓库：`/home/milesli/Desktop/RC/autoracer_hooke`
- 基线分支：`pilot-localization-sync-20260707`
- 基线提交：`98064d37638d1d515b5db2ffd68ba078c35df7b2`
- 开发分支：`rc-platform-integration`
- 制定本计划时的开发提交：`c3ffe2d496bcb5a841bab0d3d1ed85c76d26b84f`
- pilot 的 Hooke vendor 集合：99 个 ROS 包、14 个固定提交的上游仓库、1 个补丁。
- pilot 的生成链路：依赖定义和脚本由 Git 管理；`vendor_ws/src`、`build`、`install`、`log` 均为可再生结果并由 Git 忽略。

### 2.2 当前 RC 实现中的不合理部分

对比 pilot，当前 RC 分支在依赖层增加约 2082 行，并存在以下问题：

1. `dependencies/vendor-packages.tsv` 从 Hooke 已验证的 99 包扩成 103 包，`dependencies/autoracer.repos` 也加入 RC 硬件仓库，使 Hooke 默认网络导入路径受到 RC 影响；
2. `dependencies/versions.lock.yaml` 的全局包计数从 99 改成 103，但它仍只是记录文件，实际脚本不以它作为强制锁，存在双重事实来源；
3. `src/platform/rc/dependencies/` 又实现了一整套 RC 专用 resolver、import、rosdep、vendor build 和 product build；
4. RC 的 82 包集合和构建脚本中的 `== 82` 是人工冻结结果，没有证明它是当前产品依赖图的最小完整闭包；
5. “保护 Hooke”被实现成“复制一套编排”。这种隔离降低了短期回归风险，却制造了两套长期维护逻辑；
6. 当前 ADR 把共享脚本完全冻结，阻止了合理的机制复用，需要被新设计取代。

仍然正确、必须保留的原则是：

- `src/core/` 只依赖标准化 ROS 接口，不包含 Hooke 或 RC 硬件逻辑；
- RC 硬件驱动属于 RC 依赖选择，RC 自有适配器和 bringup 属于 `src/platform/rc/`；
- Fixposition、Hooke GNSS/融合定位、Hooke CAN/Nebula 等不是 RC 的映射对象；只有真实依赖图可达的包才进入 RC；
- `vendor_ws` 源码快照和所有编译产物不提交到 Git。

## 3. 机器职责

| 机器 | 本轮职责 | 允许操作 | 禁止操作 |
|---|---|---|---|
| 本机 x86 | 唯一开发主机 | 分析、写测试、修改依赖工具、生成临时 vendor 工作区、构建、静态和单元验证、提交和推送 | 不把本机成功等同于 ARM/实车成功 |
| CarMaker 机器 | Hooke 参考与最终回归机 | 第一阶段只读核对 pilot 物化结果；x86 全部通过后，在独立 checkout/工作区构建并运行原有 CarMaker 场景 | 不在已验证的原工作区上直接试改；不开发 RC；不复制整套 `vendor_ws` 回产品仓库 |
| Orin | 暂缓 | 本轮不连接、不改代码、不构建、不启动设备 | 在 x86 和 CarMaker 门禁通过前不得进入 Orin 阶段 |

本轮所有代码修改都发生在本机 x86 的 `rc-platform-integration`。CarMaker 只提供验证证据，不作为日常开发主机；Orin 不参与本计划的当前执行阶段。

## 4. 目标架构

最终只保留一套 vendor 机制，平台通过声明式 profile 选择依赖：

```text
dependencies/
├── repositories.yaml                 # 所有可用第三方仓库的唯一 URL/revision 目录
├── packages.tsv                      # package name -> source path -> repository 的唯一目录
├── profiles/
│   ├── hooke2.yaml                   # Hooke 根依赖、期望闭包和平台补丁
│   └── rc.yaml                       # RC 根依赖、期望闭包和平台补丁
└── patches/
    ├── common/
    ├── hooke2/
    └── rc/

scripts/vendor/
├── resolve_dependencies.py           # 解析、校验并输出确定性闭包
├── import_dependencies.py            # 按解析结果导入和裁剪源码
├── build_vendor.sh                   # 构建指定 profile 的 underlay
├── build_product.sh                  # 在指定 underlay 上构建产品 profile
└── environment.sh                    # 统一 ROS -> vendor -> product 的 source 顺序

scripts/import_dependencies.sh        # Hooke 兼容入口，默认行为不变
scripts/build_vendor.sh               # Hooke 兼容入口，默认行为不变
scripts/build_product.sh              # Hooke 兼容入口，默认行为不变
scripts/build.sh                      # Hooke 兼容入口，默认行为不变
```

文件名可在实施时因现有脚本复用而微调，但下列架构约束不可改变：

1. 解析、导入、补丁、包集合验证、构建、环境叠加各只有一个实现；
2. profile 只声明差异，不复制执行逻辑；
3. 不设置 profile 时，所有现有顶层命令仍等价于 pilot 的 Hooke 行为；
4. RC 必须显式指定 profile 和独立工作区，不能覆盖 Hooke `vendor_ws`；
5. repository URL/revision 只能有一个权威来源；若保留 lock 文件，它必须由权威来源生成并在 CI 中校验一致，不能继续仅作说明；
6. 闭包锁定文件可以提交，但必须能够由根依赖和固定 revision 的源码依赖图重新生成并比较；
7. 不引入新的 Python/ROS 第三方依赖来实现此工具。

## 5. 实施阶段

### 阶段 A：冻结证据并恢复 Hooke 依赖基线

**执行机器：本机 x86。**

1. 记录 pilot 与当前 RC 分支在以下路径的逐文件差异：
   - `dependencies/`
   - `scripts/`
   - `src/platform/rc/dependencies/`
2. 保存 pilot 事实：99 个包、14 个仓库、补丁列表、默认 `vendor_ws`、四个顶层入口的参数和退出行为、ROS 环境 source 顺序。
3. 为这些事实先写回归测试；测试必须能在临时目录和伪造工具下运行，不依赖 CarMaker 或 Orin。
4. 将被 RC 污染的共享清单和默认路径恢复到 pilot 语义：
   - Hooke 默认包集合重新等于 99；
   - Hooke 默认仓库集合重新等于原 14；
   - Hooke 默认脚本不再读取 RC 硬件仓库；
   - 保留 `import_dependencies.sh` 中与平台无关且已经证明必要的缺陷修复时，必须用独立测试证明，不得借 RC 需求混入。
5. 当前 `src/platform/rc/dependencies/` 暂时保留为待替换实现，避免在共享机制完成前丢失已有测试意图；它不得成为最终入口。

**门禁 A：**

- `git diff c3ffe2d496bcb5a841bab0d3d1ed85c76d26b84f -- src/core src/platform/hooke2` 为空，证明本次 vendor 工作没有继续改动既有 Core/Hooke 产品源码；
- Hooke profile/兼容入口解析结果严格为 pilot 的 99 包、14 仓库和原补丁；
- 共享文件恢复不能破坏已有 RC 产品源码；
- 回归测试先失败于当前污染，再通过于恢复后的行为。

### 阶段 B：从产品事实推导 RC 依赖闭包

**执行机器：本机 x86。**

1. 扫描下列 9 个产品包的 `package.xml`：
   - `src/core/autoracer_bringup`
   - `src/core/autoracer_control`
   - `src/core/autoracer_localization`
   - `src/core/autoracer_planning`
   - `src/core/autoracer_safety`
   - `src/core/autoracer_sensing`
   - `src/platform/rc/autoracer_rc_adapter`
   - `src/platform/rc/autoracer_rc_bringup`
   - `src/platform/rc/autoracer_rc_description`
2. 将产品包声明的第三方运行/构建依赖作为根，不把 test-only 依赖混入运行闭包。
3. 静态检查 RC 与 core launch 文件、组件容器和参数文件；若运行时加载了未在 `package.xml` 声明的包，先补齐所属产品包的依赖声明，再重新生成根集合。
4. 从固定 revision 的上游源码读取各包 `package.xml`，递归计算传递闭包；ROS 发行版系统包由 rosdep 处理，不作为 vendor 包复制。
5. 输出并审查：
   - 每个根依赖由哪个产品文件引入；
   - 每个传递依赖由哪条边引入；
   - 每个选中包属于哪个仓库及固定 revision；
   - 未被选择的 Hooke/Fixposition/Nebula/CAN 包为何不可达。
6. 将确定性结果写入 RC profile 的闭包锁定区，并添加“重新生成结果必须完全一致”的测试。

**门禁 B：**

- 不允许以 82 为预设或验收数字；最终数量由依赖图决定；
- `hipnuc_imu`、`lslidar_driver` 等只有被 RC bringup 声明并实际加载才进入；
- Fixposition 不进入 RC，理由是依赖图不可达，而不是创建人工映射或黑名单；
- `tier4_localization_launch` 若仍由 core 声明，就必须进入闭包并解决其固定源码来源，不能从旧 Hooke 工作区偷取文件。

### 阶段 C：先测试、再抽取共享机制

**执行机器：本机 x86。**

按以下顺序实施，每一步单独形成小而可回滚的 Lore commit：

1. 增加 profile schema 和解析器测试：未知包、重复包、非法路径、仓库归属歧义、revision 不一致、闭包漂移都必须失败；
2. 把当前 pilot 脚本中可用的“裁剪包、幂等补丁、精确集合校验、分层构建、环境清理”抽成共享实现；
3. 将现有顶层脚本改成薄兼容入口，未传平台参数时固定选择 `hooke2`；
4. 为 RC 增加显式入口，例如 `--profile rc --workspace /absolute/path`，并强制使用独立工作区；
5. 将 RC 硬件仓库纳入统一 repository catalog，但 Hooke profile 的导入不得访问它们；
6. 将 `versions.lock.yaml` 的职责合并到权威 catalog，或使其成为可生成且强制校验的派生锁；禁止两个文件手工维护同一 revision；
7. local refresh 模式必须校验输入源码 revision/来源清单，不能只校验最终包名；
8. 共享机制与两个 profile 等价后，删除或缩减以下重复实现：
   - `src/platform/rc/dependencies/import_rc_vendor.py`
   - `src/platform/rc/dependencies/resolve_rc_vendor.py`
   - `src/platform/rc/dependencies/build_rc_vendor.sh`
   - `src/platform/rc/dependencies/build_rc_product.sh`
   - `src/platform/rc/dependencies/install_rc_rosdeps.sh`
9. 将 `docs/design/rc-platform-vendor-scoping.md` 标记为 superseded，并用新 ADR 说明“共享机制、平台 profile、独立物化工作区”的决策。

**门禁 C：**

- 两个平台没有第二套 resolver/import/build/environment 实现；
- Hooke 兼容入口的默认参数、输出工作区、99 包集合和 source 顺序保持不变；
- RC 只新增声明性 profile、硬件依赖记录和必要薄入口；
- `git diff --check`、Python 单元测试、shell 静态检查及全部依赖合同测试通过；
- `git diff c3ffe2d496bcb5a841bab0d3d1ed85c76d26b84f -- src/core src/platform/hooke2` 仍为空。

### 阶段 D：解决上游源码的可再生性

**主要执行机器：本机 x86；CarMaker 机器只读协助。**

1. 在 x86 上从干净临时目录执行所有公开仓库的固定 revision 网络导入；
2. 对私有 `autoware_launch.x1` 或其他不可访问来源，在 CarMaker 机器只读记录：远程 URL、当前 commit、所需包路径、是否存在本地补丁；
3. 选择一种正式恢复方式并写入 repository catalog：
   - 可访问的固定 Git 远程；或
   - 受控镜像的固定 commit；或
   - 带来源元数据和 SHA-256 的源码归档。
4. 禁止把 CarMaker 的整个 `vendor_ws/src` 直接提交，禁止用未校验的目录复制绕过来源门禁；
5. 新机器恢复测试必须从空目录得到相同仓库 revision、包集合和补丁结果。

**门禁 D：**所有 RC 闭包内的源码都可从记录的权威来源重建。任一私有来源未解决时，只能报告“源码合同测试通过、完整导入受阻”，不能报告 vendor 构建完成。

### 阶段 E：本机 x86 完整验证

**执行机器：本机 x86。**

使用临时目录，不能复用历史 `vendor_ws/build/install` 来掩盖缺包：

1. 干净 Hooke profile 导入：精确发现 99 包，无额外 RC 硬件仓库访问；
2. 干净 Hooke vendor 构建；
3. 在该 underlay 上构建 Hooke 产品；
4. 干净 RC profile 导入：精确等于阶段 B 的派生闭包；
5. 干净 RC vendor 构建；
6. 在该 underlay 上构建 `src/core + src/platform/rc`，目标到 `autoracer_rc_bringup`；
7. 验证环境顺序为 `/opt/ros/humble -> 指定 vendor install -> 指定 product install`，并验证旧 Autoware/Conda 前缀不会泄漏；
8. 运行全部单元、合同、lint 和静态测试；记录命令、退出码和日志位置。

**门禁 E：**两套干净构建均成功；没有 tracked `vendor_ws`、`build`、`install`、`log`；不存在已知测试失败；Core 和 Hooke 产品源码无 RC 改动。

### 阶段 F：CarMaker Hooke 回归

**执行机器：CarMaker 机器；只有阶段 A-E 全部通过后才开始。**

1. 不修改原已验证 checkout 和原 `vendor_ws`；创建独立 checkout 和独立临时 vendor/product 工作区；
2. 拉取 x86 已提交的候选 commit；
3. 运行 Hooke 默认兼容入口，确认仍得到 99 包和相同补丁；
4. 构建 Hooke vendor 与产品 overlay；
5. 使用该候选产物运行现有 CarMaker 验证场景；
6. 对比 pilot 验证记录中的节点、topic、TF、地图、定位、规划、控制和安全链路；
7. 保存 commit SHA、依赖解析摘要、构建日志和场景结果。

**门禁 F：**CarMaker 场景达到原 pilot 的通过标准。失败时停止进入下一阶段，在 x86 上修复并重新走 E、F；不能以“结构上应当等价”替代实际回归。

## 6. Orin 的未来进入条件

Orin 不属于本轮执行，但未来只有同时满足以下条件才允许开始：

- 阶段 A-F 全部通过；
- 候选 commit 已推送且两台验证机使用同一 SHA；
- RC vendor 源码可从空目录完整恢复；
- x86 的 RC vendor 和产品构建通过；
- CarMaker 的 Hooke 回归通过；
- 文档明确 RC 设备参数、串口、LiDAR/IMU topic、TF 和控制输出合同；
- 不存在通过复制旧 Orin Autoware/Quick Start 目录才能运行的隐式依赖。

进入 Orin 后，它只负责 ARM 编译差异、设备驱动、实时 topic/TF、定位、规划、控制输出和整车链路验证；通用依赖工具仍在 x86 主开发仓库维护。

## 7. 提交策略

禁止把全部重构压成一个提交。建议顺序：

1. `Lock the validated Hooke dependency behavior before convergence`
2. `Restore the CarMaker-proven dependency baseline before adding profiles`
3. `Make platform dependency closures reproducible from one catalog`
4. `Reuse one vendor pipeline without changing Hooke defaults`
5. `Remove the duplicate RC dependency orchestration`
6. `Prove clean Hooke and RC workspaces are reproducible`

每个提交遵循仓库 Lore Commit Protocol，至少记录 `Constraint`、`Rejected`、`Confidence`、`Scope-risk`、`Tested` 和 `Not-tested`。不得重写 pilot 分支；所有修改只追加到 `rc-platform-integration`。

## 8. 最终验收清单

- [ ] `pilot-localization-sync-20260707` 仍指向 `98064d37638d1d515b5db2ffd68ba078c35df7b2`；
- [ ] `src/core/` 与 `src/platform/hooke2/` 相对本计划的起始提交 `c3ffe2d` 无新增改动；
- [ ] Hooke 默认入口仍解析 99 包、14 仓库和原补丁；
- [ ] RC 包数量由固定源码依赖图生成，未写死 82；
- [ ] Hooke 与 RC 共用唯一 resolver/import/build/environment 机制；
- [ ] RC 与 Hooke 使用独立的可丢弃工作区；
- [ ] Fixposition/GNSS/CAN/Nebula 不因“旧车映射”进入 RC；
- [ ] repository URL/revision 只有一个权威来源且可验证；
- [ ] 从空目录完成两套 x86 导入和构建；
- [ ] CarMaker 独立工作区完成 Hooke 回归；
- [ ] 本轮没有连接或修改 Orin；
- [ ] `vendor_ws/`、`build/`、`install/`、`log/` 均未被 Git 跟踪；
- [ ] 所有测试、日志、commit SHA 和未测试项均有明确记录。

## 9. 停止条件

本计划当前只交付设计，不自动实施。后续执行时，仅在以下情况暂停并报告：

- 需要删除或覆盖 CarMaker 已验证工作区；
- 固定私有源码无法取得且不存在受控镜像/归档；
- 依赖闭包要求修改 Core 的公开接口或改变 Hooke 产品行为；
- x86 或 CarMaker 的既有通过标准无法复现。

除此之外，执行者应按阶段顺序推进，任何阶段失败都在当前阶段修复并重新验证，不得跳过门禁进入 Orin。
