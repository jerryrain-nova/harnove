# Harnove

Harnove 是一个面向代码研发的迭代 Harness。它提供“专家模式”和“敏捷模式”，
把一次需求从澄清、方案设计、代码实现推进到迭代总结，并在关键阶段保留人工审核
闸门。

Harnove 的主 Agent 只负责流程编排；每个阶段和文档版本都由全新的隔离子 Agent
完成。方案设计直接读取当前仓库代码，代码实施前会创建独立 Git 分支，所有文档、
反馈、执行结果和 Git 证据都会保存在项目内的 Harnove 目录中。

## 开始前准备

使用 Harnove 前，请确认：

- 已安装 Python 3.10 或更高版本。
- 目标项目是 Git 仓库。
- 使用支持子 Agent 的 Codex、Claude Code 或 Cursor。
- 已有一份本地 PRD，或者可以直接提供自然语言需求。

GitHub CLI、Homebrew 和 Node.js 不是 Harnove 的安装依赖。
如果尚未安装 Python，可以从 [Python 官方网站](https://www.python.org/downloads/)
下载安装。若当前 Agent 环境不支持子 Agent，Harnove 会在开始派发时停止并明确提示，
不会降级为不隔离的执行方式。

## 1. 下载 Harnove

打开 [Harnove GitHub 仓库](https://github.com/jerryrain-nova/harnove)，选择
`Code → Download ZIP`，解压后把整个目录复制到目标项目根目录，并命名为
`harnove`：

```text
your-project/
├─ harnove/
│  ├─ init.py
│  ├─ run.ps1
│  ├─ scripts/
│  └─ SKILL.md
├─ src/
└─ ...
```

ZIP 解压后的目录通常名为 `harnove-main`。移动或重命名时要确保最终路径是
`your-project/harnove/init.py`，不要形成
`your-project/harnove/harnove-main/init.py` 的双层目录。

也可以把 Harnove 放在 `tools/harnove/` 等工具目录。后续命令中的路径需要相应调整。

## 2. 初始化到项目

进入目标项目根目录。

macOS / Linux：

```bash
python3 harnove/init.py --project .
```

Windows PowerShell：

```powershell
python .\harnove\init.py --project .
```

如果 Harnove 位于项目目录之外，也可以使用绝对路径执行 `init.py`。这种情况下，
Harnove 会安装到目标项目的 `.harnove/` 中：

```bash
python3 /path/to/harnove/init.py --project /path/to/your-project
```

初始化会完成以下工作：

- 创建运行时、配置、迭代归档和经验目录。
- 安装 Codex 的 `.agents/skills/harnove/` 入口。
- 安装 Claude Code 的 `.claude/skills/harnove/` 入口。
- 安装 Cursor 的 `.cursor/commands/harnove.md` 入口。
- 保留项目自己维护的配置和个性化规则。

看到 `Harnove 初始化完成` 后，把目标 Git 项目根目录作为工作区重新打开，并新建
Agent 会话，让平台重新发现 Skill。通常不需要重启整台电脑；如果当前应用仍无法
发现入口，再重新打开应用窗口。

## 3. 启动第一个迭代

推荐直接向 Agent 描述需求，由 Agent 驱动 Harnove 状态机，不需要手工执行每条底层
命令。开始前需要选择专家模式或敏捷模式；未指定时默认使用专家模式。

专家模式适合需要完整产品、技术、测试设计和测试执行的需求，流程为：

```text
需求澄清 → 产品方案 → 技术方案 → 代码方案 → 测试方案
→ 代码实现 → 测试执行 → 迭代总结
```

敏捷模式适合边界清楚、希望快速进入实现的小型迭代，流程为：

```text
需求澄清 → 代码方案 → 代码实现 → 迭代总结
```

敏捷模式会省略产品方案、技术方案、测试方案和测试执行阶段，但仍遵守 `custom/`
中的项目约束。代码方案阶段只描述改动方案，不修改实际代码；进入代码实现前仍必须
经过人工明确批准。

Codex 专家模式示例：

```text
使用 $harnove，以专家模式启动 ITER-20260723-001 迭代。
需求名称：order-export。
需求：在订单列表增加批量导出；格式和数量上限还没有确定。
```

Codex 敏捷模式示例：

```text
使用 $harnove，以敏捷模式启动 ITER-20260723-002 迭代。
需求名称：order-export。
需求：在订单列表增加批量导出 CSV，单次最多 1000 条。
```

Claude Code 或 Cursor 可以使用 `/harnove`：

```text
/harnove 以敏捷模式启动 ITER-20260723-002，需求名称 order-export：
在订单列表增加批量导出 CSV，单次最多 1000 条。
```

如果已有 PRD，可以直接提供路径：

```text
使用 $harnove，以专家模式基于 docs/prd/order-refund.md
启动 ITER-20260723-003 迭代。需求名称：order-refund。
```

Harnove 会先建议一个适合分支名的迭代名称。你需要明确回复采用该名称，或者输入
自己的名称；确认前不会正式初始化迭代。

三个名称的用途不同：

- 迭代 ID：一次迭代的唯一编号，例如 `ITER-20260723-001`。推荐包含日期和当日序号，
  但工具不强制固定格式；不要复用已有 ID。
- 需求名称：稳定、简短的需求标识，例如 `order-export`，会进入归档和文档名称。
- 迭代名称：由 Agent 建议并由你确认，默认用于实施分支名。

可以直接回复：`采用建议名称`，也可以回复：`迭代名称改为 order-batch-export`。
默认归档目录格式为 `<YYYYMMDD>_<迭代 ID>_<需求名称>`，其中日期是创建迭代当天。

如需使用底层命令，可通过 `--mode expert` 或 `--mode agile` 明确指定模式。

## 4. 配合人工审核

专家模式会依次推进以下阶段：

1. 候选 PRD
2. 产品方案
3. 技术方案
4. 代码修改方案
5. 测试方案
6. 代码实施
7. 测试执行
8. 迭代总结

敏捷模式会依次推进以下阶段：

1. 需求澄清
2. 代码修改方案
3. 代码实施
4. 迭代总结

敏捷模式的需求澄清会确定需求边界和模糊点。只有用户明确确认“澄清完毕”并批准
完整需求基线后，才能进入代码方案阶段。

专家模式的候选 PRD、产品方案、技术方案、代码方案和测试方案，以及敏捷模式的需求
澄清和代码方案，都必须由用户人工审核；Harnove 不会自行判断通过。

- 如果文档可以直接使用，明确回复“批准”或“通过”。
- 如果需要修改，直接给出反馈。
- 收到反馈后，主 Agent 会先说明哪些章节会变化、为什么变化以及哪些边界保持不变。
- 只有你批准这份变更影响说明后，Harnove 才会创建下一文档版本并派发新的子 Agent。
- 你也可以继续补充反馈；主 Agent 会重新归纳影响范围并再次询问。

Agent 会在每个审核点给出产物的实际文件路径。可以点击路径打开文档，也可以直接
要求 Agent 展示或总结当前待审核版本。批准变更影响说明只允许生成下一版，并不等于
批准下一版文档；新版本产出后仍需再次审核。

历史版本不会被覆盖。v002 及后续版本会用精简的“版本演进摘要”，按当前版本到
v001 的顺序展示完整迭代轨迹。

## 5. 代码分支和项目结构

代码实施阶段会先创建并切换独立分支。默认格式为：

```text
tmp/{迭代名称}-{实施轮次}
```

例如：

```text
tmp/order-export-1
```

如果你提前指定了分支命名规则，Harnove 会优先使用你的规则。
如果目标分支已经存在或 Git 工作区状态导致无法安全切换，Harnove 会停止并报告，
需要先由用户决定复用、改名或整理工作区。

需求、技术方案和代码方案始终以当前仓库代码为架构依据，不会从 `structure/`
读取代码框架。只有总结阶段，才会把完成后的项目结构抽象写入 `structure/`，
供人阅读和后续总结使用。

专家模式测试失败并需要修改代码时，Harnove 会询问是在原实施分支修复，还是创建
新分支修复。选择原分支时，修复与最终交付都留在同一实施分支；选择新分支时，
会沿用实施轮次的分支切换规则。修复后会再次执行测试。

专家模式下，所有必测项通过且迭代总结成功归档后，迭代状态才是 `complete`。
敏捷模式不运行独立测试阶段，最终总结会明确记录 `AGILE_TEST_STATUS: NOT_RUN`，
并向用户展示代码改动点。总结阶段不再设置额外人工审核闸门。

## 6. 查看迭代状态

通常直接询问 Agent“当前 Harnove 迭代状态”即可。也可以手工执行状态命令。

macOS / Linux：

```bash
python3 harnove/runtime/harnove.py status \
  --archive harnove/iterations/20260723_ITER-20260723-001_order-export
```

Windows PowerShell：

```powershell
.\harnove\run.ps1 status `
  --archive .\harnove\iterations\20260723_ITER-20260723-001_order-export
```

如果使用外置安装，请把 `harnove/` 替换为 `.harnove/`。

## 7. Harnove 数据保存在哪里

项目内安装时，所有运行数据都在实际的 Harnove 工具目录下。默认是 `harnove/`；
如果安装在 `tools/harnove/`，对应目录就是 `tools/harnove/iterations/` 等：

```text
harnove/
├─ config.json          项目配置
├─ iterations/          每次迭代的文档、审核和执行证据
├─ improve/             跨迭代复用经验
├─ structure/           完成迭代后的项目结构抽象
└─ custom/
   ├─ user.md           项目长期约束和偏好
   └─ self.md           从历史反馈中提炼的经验
```

外置安装时，这些内容位于项目的 `.harnove/` 下。首次外置安装完成后，日常运行只
依赖项目内的 `.harnove/`；外部源码目录仅在以后重新安装或升级时需要。

单次迭代目录内，常用产物位置如下：

```text
iterations/<YYYYMMDD>_<迭代 ID>_<需求名称>/
├─ 00-input/                原始输入和候选 PRD
├─ 01-technical-design/     技术方案
├─ 02-code-plan/            代码修改方案
├─ 03-test-design/          测试方案
├─ 04-implementation/       实施记录
├─ 05-test-execution/       测试执行结果
├─ 06-summary/              最终迭代总结
├─ reviews/                 人工审核与变更影响记录
├─ agent-runs/              子 Agent 工作单和执行证据
└─ state.json               当前流程状态
```

敏捷模式沿用同一归档结构，但只在实际经过的阶段写入产物。最终总结文件位于
`06-summary/`，名称格式为 `<迭代 ID>_<需求名称>_迭代总结_vNNN.md`。
Agent 在每个阶段也会返回当前产物的完整路径。

## 8. 升级 Harnove

用新版发行目录替换 Harnove 的核心文件后，在项目根目录重新执行初始化命令：

```bash
python3 harnove/init.py --project .
```

初始化是幂等的，不会删除 `iterations/`、`improve/`、`structure/`、`custom/` 或项目
配置。如果检测到用户手工修改过受托管的核心文件，升级会停止并报告冲突。

只有确认要用新版覆盖这些人工修改时，才执行：

```bash
python3 harnove/init.py --project . --force-managed-files
```

## 9. 常见问题

### 找不到 `python` 或 `python3`

安装 Python 3.10+，重新打开终端后执行 `python3 --version` 或 `python --version`
确认环境。

### 提示找不到 `runtime/harnove.py`

说明还没有完成初始化，或者执行命令时使用了错误的 Harnove 路径。回到项目根目录
重新执行 `init.py --project .`。

### Agent 找不到 `$harnove` 或 `/harnove`

确认初始化成功后，重新打开 Codex、Claude Code 或 Cursor 会话。还可以检查项目中
是否存在 `.agents/skills/harnove/`、`.claude/skills/harnove/` 或
`.cursor/commands/harnove.md`。

### 提示当前平台不能创建子 Agent

隔离子 Agent 是 Harnove 的安全边界，不能跳过。请切换到支持子 Agent 的平台或环境。

### 我可以直接修改 `state.json` 吗

不可以。`state.json` 是流程状态的唯一权威来源，必须通过 Harnove 命令推进。

## 进一步阅读

- [完整使用手册](USAGE.md)
- [Agent 工作流约束](SKILL.md)
- [文档与审核产物契约](references/artifact-contracts.md)
