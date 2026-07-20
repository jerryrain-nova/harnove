# 研发迭代 Harnove 使用手册

## 1. 工具用途

本工具用于按照 PRD 驱动一次完整代码迭代，并强制执行以下流程：

1. 技术方案设计与人工审核。
2. 代码修改方案设计与人工审核。
3. 测试方案设计与人工审核。
4. 按批准方案实施代码变更。
5. 编写并执行测试；失败时退回代码实施阶段。
6. 测试全部通过后生成迭代总结、评分和改进项。

任何 Agent 都不能代替人工通过前三个审核闸门。所有文档、审核意见、Git 证据和测试结果均保存在同一个 Harnove 目录中。

## 2. 环境要求

- Python 3.10 或更高版本。
- 目标项目应使用 Git；没有可用 Git 仓库时仍能运行，但只能生成 Git 不可用记录。
- PRD 必须是本地可读取文件。
- Windows 用户可以使用 `run.ps1`；macOS/Linux 用户直接运行 Python 脚本。

## 3. 放入项目

推荐把整个发行目录复制到目标项目根目录，并保留名称 `harnove`：

```text
your-project/
├─ harnove/
│  ├─ init.py
│  ├─ run.ps1
│  ├─ SKILL.md
│  ├─ scripts/
│  └─ references/
├─ src/
└─ ...
```

也可以放在项目已有的工具目录中，例如 `tools/harnove/`。初始化产生的所有 Harnove 子目录都会放在该工具目录内部，不会在项目根目录创建 `.agents`、`docs/iterations` 等额外目录。

## 4. 初始化项目

在项目根目录执行：

```powershell
python harnove/init.py --project .
```

如果工具位于 `tools/harnove`：

```powershell
python tools/harnove/init.py --project .
```

初始化完成后的统一目录结构如下：

```text
harnove/
├─ config.json                       项目配置，归项目维护
├─ install-manifest.json             插件托管文件及哈希
├─ run.ps1                           Windows 命令入口
├─ runtime/
│  └─ harnove.py                     状态机运行时
├─ skill/
│  └─ run-harnove-iteration/
│     ├─ SKILL.md                    Agent 流程约束
│     ├─ agents/openai.yaml
│     └─ references/artifact-contracts.md
└─ iterations/                       所有迭代归档
```

自定义归档子目录名称：

```powershell
python harnove/init.py --project . --archive-dir iteration-records
```

`--archive-dir` 只能指向 Harnove 目录内部，防止归档再次散落到项目其他位置。

## 5. 让 Agent 使用流程

向 Agent 发起任务时，明确要求它读取初始化后的 Skill：

```text
请读取 harnove/skill/run-harnove-iteration/SKILL.md，
并严格按照该流程，基于 docs/prd/order-refund.md 启动 ITER-20260720-001 迭代。
```

如果工具放在 `tools/` 下，应使用实际路径。Agent 必须先确认 `config.json` 存在，不能自行跳过项目初始化。

## 6. 启动一次迭代

Windows：

```powershell
.\harnove\run.ps1 init `
  --iteration-id ITER-20260720-001 `
  --requirement order-refund `
  --prd docs/prd/order-refund.md
```

macOS/Linux 或直接使用 Python：

```bash
python harnove/runtime/harnove.py init \
  --iteration-id ITER-20260720-001 \
  --requirement order-refund \
  --prd docs/prd/order-refund.md
```

工具会复制 PRD、记录 SHA-256 和 Git 基线，并创建如下迭代目录：

```text
harnove/iterations/
└─ 20260720_ITER-20260720-001_order-refund/
   ├─ 00-input/
   ├─ 01-technical-design/
   ├─ 02-code-plan/
   ├─ 03-test-design/
   ├─ 04-implementation/
   ├─ 05-test-execution/
   ├─ 06-summary/
   ├─ reviews/
   └─ state.json
```

命令输出会给出当前需要填写的文档路径。

## 7. 查看当前状态

```powershell
.\harnove\run.ps1 status --archive <迭代目录>
```

主要状态：

- `drafting`：当前角色应填写指定文档。
- `awaiting_human_review`：等待人工审批，Agent 必须停止推进。
- `complete`：测试通过且总结已经归档。

`state.json` 是流程状态的唯一权威来源，不要人工修改。

## 8. 提交阶段文档

完成当前文档后执行：

```powershell
.\harnove\run.ps1 submit --archive <迭代目录>
```

提交前会检查：

- 必需章节是否齐全。
- 是否存在 `REQ-xxx` 需求依据。
- 是否残留模板占位符。
- 文档是否具备基本可审核内容。

技术方案、代码修改方案和测试方案提交后都会进入人工审核状态。

## 9. 人工审核

批准：

```powershell
.\harnove\run.ps1 review `
  --archive <迭代目录> `
  --decision approve `
  --reviewer "张三"
```

驳回：

```powershell
.\harnove\run.ps1 review `
  --archive <迭代目录> `
  --decision reject `
  --reviewer "张三" `
  --feedback "补充 REQ-003 的数据库回滚和兼容策略"
```

驳回必须包含可执行反馈。工具会保留原文档和审核记录，并创建下一个文档版本，不会覆盖历史版本。

## 10. 代码实施和 Git 证据

前三个闸门全部批准后，代码专家才能修改业务代码。完成代码修改记录后执行普通 `submit`。

工具会自动归档：

- 当前 Git HEAD。
- `git status --short`。
- `git diff --stat`。
- 完整二进制安全 patch。

代码实际变更若偏离批准方案，必须先取得人工批准，并在代码变更记录中说明依据。

## 11. 测试执行与失败回退

测试专家必须基于实际 Git diff 和已批准测试方案编写、运行可执行测试。

全部通过：

```powershell
.\harnove\run.ps1 submit --archive <迭代目录> --result passed
```

存在失败：

```powershell
.\harnove\run.ps1 submit --archive <迭代目录> --result failed
```

失败后流程自动返回代码实施阶段，并创建新的实施版本。修复后重新实施、重新测试，直到全部强制测试通过。

## 12. 完成迭代

测试通过后，流程进入总结阶段。总结文档必须包含：

- 需求背景和批准范围。
- 实际代码变更。
- 测试结论和剩余风险。
- 需求、方案、代码和测试追溯矩阵。
- 技术方案、代码方案、测试设计、实施、测试执行和整体流程评分。
- 亮点、缺点、根因和下次迭代改进项。

提交总结后，状态变为 `complete`。

## 13. 配置

初始化后可以编辑 `config.json`。常用字段：

```json
{
  "project_root": "..",
  "repo_root": ".",
  "archive_root": "iterations",
  "skill": "skill/run-harnove-iteration",
  "scope_policy": "prd_only",
  "test_pass_policy": "all_mandatory_cases_pass"
}
```

- `project_root`：从 Harnove 目录到项目根目录的相对路径。
- `repo_root`：从项目根目录到 Git 仓库的相对路径。
- `archive_root`：从 Harnove 目录到迭代归档目录的相对路径。
- `scope_policy`：必须保持 `prd_only`，所有变更只能来自 PRD。

重复初始化不会覆盖已有 `config.json`。

## 14. 更新 Harnove

用新版发行文件替换工具源文件后，重新执行：

```powershell
python harnove/init.py --project .
```

初始化器根据 `install-manifest.json` 判断托管文件是否被人工修改：

- 未修改：自动更新。
- 已修改：停止更新并列出冲突文件。
- 明确接受覆盖：添加 `--force-managed-files`。

```powershell
python harnove/init.py --project . --force-managed-files
```

强制覆盖只适用于插件托管的运行时和 Skill 文件，不覆盖项目的 `config.json` 和已有迭代归档。

## 15. 常见问题

### 找不到 Python

安装 Python 3.10+，或使用 Python 可执行文件的绝对路径调用 `init.py` 和 `runtime/harnove.py`。

### Git 证据显示不可用

确认 `project_root`、`repo_root` 正确，并确认目标目录是有效 Git 仓库且系统能执行 `git`。

### Agent 想跳过人工审核

不要修改 `state.json`。只有人工执行 `review --decision approve` 才能推进闸门。

### PRD 没有需求编号

在迭代的需求基线文档中按原意建立 `REQ-001` 等稳定编号，不得借此增加 PRD 未表达的范围。

### 文档提交失败

根据命令输出补齐章节、需求 ID 和证据，删除所有模板占位符后重新提交。

## 16. 单独迭代 Harnove 功能

Harnove 核心和项目运行内容必须分开处理。

核心文件由 `harnove-package.json` 的 `core_files` 白名单定义，主要包括：

- `init.py` 和 `run.ps1`。
- 根目录 `SKILL.md`、`agents/` 和 `references/`。
- `scripts/harnove.py` 状态机源码。
- 使用文档、自测和打包脚本。

以下内容属于使用方项目，不得作为 Harnove 功能提交或进入发行包：

- `config.json`。
- `install-manifest.json`。
- `iterations/` 中的 PRD、方案、审核、代码和测试记录。
- 初始化生成的 `runtime/` 和 `skill/` 副本。
- 业务项目源代码、Git diff、日志和测试数据。

优化 Harnove 时，应修改核心源文件。例如状态机功能修改 `scripts/harnove.py`，不要直接修改生成的 `runtime/harnove.py`；Agent 流程修改根目录 `SKILL.md`，不要直接修改生成的 `skill/` 副本。

完成修改后更新 `harnove-package.json` 中的版本号，并执行三组自测：

```powershell
python harnove/scripts/self_test.py
python harnove/scripts/install_self_test.py
python harnove/scripts/package_self_test.py
```

导出不包含项目内容的干净发行目录：

```powershell
python harnove/scripts/export_package.py `
  --source harnove `
  --output releases/harnove-2.1.0
```

输出目录必须不存在或为空。打包器只复制核心白名单文件，因此未知项目文件也不会被误带入。输出中的 `package-build.json` 记录版本、配置 Schema 和所有发行文件的 SHA-256，可用于交付校验。

把新发行包放入其他项目后重新执行 `init.py` 即可升级。项目自己的配置和历史迭代归档不会被覆盖。
