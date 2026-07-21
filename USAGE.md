# 研发迭代 Harnove 使用手册

## 1. 工具用途

本工具可从现有 PRD 或自然语言需求启动一次完整代码迭代，并强制执行以下流程：

1. 创建或补齐候选 PRD，并由用户人工审核。
2. 技术方案设计与人工审核。
3. 代码修改方案设计与人工审核。
4. 测试方案设计与人工审核。
5. 按批准方案实施代码变更。
6. 编写并执行测试；失败时退回代码实施阶段。
7. 测试全部通过后生成迭代总结、评分和改进项。

技术方案和代码修改方案会在关系复杂时使用 Mermaid 图辅助审核。每个环节由
全新的隔离子 Agent 执行，主 Agent 只编排进度、处理人工交互和推进状态机。
项目解读会持续保存在 `harnove/structure/`：优先复用已有记录，空目录时才扫描
整个项目，并按功能模块、代码框架、结构定义和关系进行拆解。

任何 Agent 都不能代替用户通过 PRD 及后续人工审核闸门。所有文档、审核意见、Git 证据和测试结果均保存在同一个 Harnove 目录中。

## 2. 环境要求

- Python 3.10 或更高版本。
- 目标项目应使用 Git；没有可用 Git 仓库时仍能运行，但只能生成 Git 不可用记录。
- 初始输入必须是本地可读取的 PRD，或一段非空的自然语言需求描述。
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
│  └─ harnove/
│     ├─ SKILL.md                    Agent 流程约束
│     ├─ agents/openai.yaml
│     └─ references/artifact-contracts.md
├─ iterations/                       所有迭代归档
├─ improve/                          跨迭代持续积累的可复用经验
└─ structure/                        当前项目结构解读与关系记录
```

自定义归档子目录名称：

```powershell
python harnove/init.py --project . --archive-dir iteration-records
```

`--archive-dir` 只能指向 Harnove 目录内部，防止归档再次散落到项目其他位置。

## 5. 让 Agent 使用流程

向 Agent 发起任务时，明确要求它读取初始化后的 Skill：

```text
请读取 harnove/skill/harnove/SKILL.md，
并严格按照该流程，基于 docs/prd/order-refund.md 启动 ITER-20260720-001 迭代。
```

也可以直接描述需求：

```text
/harnove 启动 ITER-20260720-002，需求名 order-export：
在订单列表增加批量导出。请先把我的描述整理为候选 PRD；不明确的边界先问我。
```

如果工具放在 `tools/` 下，应使用实际路径。主 Agent 必须先确认 `config.json`
存在，不能自行跳过初始化，也不能亲自编写环节文档、产品代码或测试。每个
环节/版本必须调用平台原生能力创建一个从未使用过的子 Agent。

## 6. 启动一次迭代

### 6.1 使用现有 PRD

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

工具会只读复制原始 PRD、记录 SHA-256，并另外创建一份候选 PRD。Agent 可以在
候选文档中补充形成明确范围和验收标准所必需的信息，但必须注明补充依据和原因，
不得修改源 PRD 或归档的原始副本。现有 PRD 同样需要经过 PRD 人工审核后才能继续。

随后会创建如下迭代目录：

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
   ├─ agent-runs/
   └─ state.json
```

命令输出会给出当前产物路径和子 Agent 派发提示。该归档只能位于
`harnove/iterations/`（外置安装时为 `.harnove/iterations/`）。

### 6.2 使用自然语言描述

短描述可直接传入：

```powershell
.\harnove\run.ps1 init `
  --iteration-id ITER-20260720-002 `
  --requirement order-export `
  --description "在订单列表增加批量导出，但格式和数量上限还没确定。"
```

较长描述建议放入文本文件，避免命令行转义问题：

```powershell
.\harnove\run.ps1 init `
  --iteration-id ITER-20260720-002 `
  --requirement order-export `
  --description-file .\requirements\order-export.txt
```

此模式首先进入 `prd_intake`。Agent 会保留原始输入，创建一份带稳定
`REQ-xxx` 编号的候选 PRD，并把会影响范围、设计或验收的模糊边界列入
“待确认问题”。如果仍需确认，Agent 提交：

```powershell
.\harnove\run.ps1 submit `
  --archive <迭代目录> `
  --result needs-clarification
```

用户回答后，把原始回答归档并生成下一版候选 PRD：

```powershell
.\harnove\run.ps1 clarify `
  --archive <迭代目录> `
  --responder "产品负责人" `
  --response "导出 CSV；单次最多 10,000 条。"
```

Agent 根据回答修订新版本。如仍有关键歧义则继续询问；全部边界明确后，将
状态标记改为 `PRD_STATUS: READY`，并在“待确认问题”中写
`无（边界已确认）`，然后执行：

```powershell
.\harnove\run.ps1 submit --archive <迭代目录> --result ready
```

此时状态进入 `awaiting_prd_review`，不会自动进入技术设计。用户必须审核完整
候选 PRD：

```powershell
.\harnove\run.ps1 review `
  --archive <迭代目录> `
  --decision approve `
  --reviewer "产品负责人"
```

如果不通过，必须给出修改建议：

```powershell
.\harnove\run.ps1 review `
  --archive <迭代目录> `
  --decision reject `
  --reviewer "产品负责人" `
  --feedback "REQ-003 需要补充无权限用户的处理边界"
```

驳回会保留被审核版本和审核记录，并生成下一版候选 PRD。Agent 按反馈修改后
重新提交，直到用户批准。只有批准版本才会冻结为后续技术方案、代码方案、测试
及实施的需求基线。原始输入、所有候选版本及用户补充均保留在 `00-input/` 中。

PRD 批准后先进入 `structure_analysis`。如果 `structure/` 已有记录，子 Agent 先
读取记录，再检查需求相关代码是否一致；如果为空，则读取项目整体代码，并按
“功能模块、代码框架、结构定义和关系”创建结构记录。结构不一致必须先更新，
然后才能进入技术方案。

## 7. 查看当前状态

```powershell
.\harnove\run.ps1 status --archive <迭代目录>
```

主要状态：

- `awaiting_dispatch`：主 Agent 必须创建全新子 Agent 并派发 work order。
- `subagent_working`：子 Agent 正在隔离执行，主 Agent 只监控进度。
- `ready_for_submit`：子 Agent 已完成，主 Agent 可以校验并提交。
- `awaiting_user_clarification`：候选 PRD 等待用户补齐边界，不能进入技术设计。
- `awaiting_prd_review`：候选 PRD 等待用户正式审批，Agent 不得自行通过。
- `awaiting_human_review`：等待人工审批，Agent 必须停止推进。
- `complete`：测试通过且总结已经归档。

`state.json` 是流程状态的唯一权威来源，不要人工修改。

### 7.1 子 Agent 派发与隔离

每个环节都执行相同的调度协议。主 Agent 先选择一个本次迭代从未使用过的子
Agent ID，然后创建 work order：

```powershell
.\harnove\run.ps1 dispatch `
  --archive <迭代目录> `
  --agent-id "technical-design-v1-agent" `
  --orchestrator "main-agent"
```

主 Agent 使用 Codex、Cursor 或 Claude Code 的原生子 Agent 能力，把输出中的
work-order 文件交给全新子 Agent。子 Agent 只执行当前环节，不调用 Harnove
状态命令，不进行人工审批。完成后由主 Agent 登记结果：

```powershell
.\harnove\run.ps1 agent-complete `
  --archive <迭代目录> `
  --run-id <dispatch输出的run-id> `
  --result succeeded `
  --evidence "已完成产物并返回文件、命令和验证摘要"
```

失败使用 `--result failed`；崩溃或超时使用 `abandon --run-id <run-id> --reason
"子 Agent 超时"`。之后必须使用新的 Agent ID 重新派发。状态机拒绝复用 Agent
ID，也拒绝没有成功子 Agent 记录的产物提交。

## 8. 提交阶段文档

子 Agent 成功完成、状态变为 `ready_for_submit` 后，由主 Agent 执行：

```powershell
.\harnove\run.ps1 submit --archive <迭代目录>
```

提交前会检查：

- 必需章节是否齐全。
- 是否存在 `REQ-xxx` 需求依据。
- 是否残留模板占位符。
- 文档是否具备基本可审核内容。
- 技术方案和代码方案是否包含有效 Mermaid 图，或给出具体的不适用理由。

技术方案、代码修改方案和测试方案提交后都会进入人工审核状态。

技术方案的“架构与流程图”和代码方案的“改动关系图”使用：

```text
DIAGRAM_STATUS: INCLUDED
```

并提供 `mermaid` 代码块。只有图不能提升理解时才使用
`DIAGRAM_STATUS: NOT_APPLICABLE`，且必须给出至少 20 字的具体理由。

此外，技术方案必须包含“功能变更树”，代码方案必须包含“代码变更树”，例如：

```text
订单导出需求
├── 查询条件复用
├── 权限边界
└── 文件生成与下载
```

两类文档默认声明 `PRESENTATION_FORMAT: MD`。只有 Markdown 无法精准表达复杂关系
时，才改为 `PRESENTATION_FORMAT: HTML`，并在同一归档目录生成同名 `.html`
辅助文件；Markdown 主文档仍必须保留变更树、依据和追溯信息。

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

PRD、技术方案、代码方案和测试方案四个闸门全部批准后，代码专家才能修改业务代码。完成代码修改记录后执行普通 `submit`。

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
- 亮点、缺点、根因、经验总结、下次复用规则和改进项。

测试通过后先进入 `structure_refresh`，子 Agent 必须依据实际 Git diff 更新
`harnove/structure/`，并通过结构哈希和内容校验；随后才进入总结。

提交总结后，状态变为 `complete`，并在 `harnove/improve/` 新增一份不可变经验
记录。下一次需求初始化时会把全部历史经验和哈希快照到该迭代的 `00-input/`
经验复用上下文中，供所有子 Agent 采用。每次总结新增文件，不覆盖旧经验。

## 13. 配置

初始化后可以编辑 `config.json`。常用字段：

```json
{
  "project_root": "..",
  "repo_root": ".",
  "archive_root": "iterations",
  "improve_root": "improve",
  "structure_root": "structure",
  "skill": "skill/harnove",
  "scope_policy": "prd_only",
  "test_pass_policy": "all_mandatory_cases_pass"
}
```

- `project_root`：从 Harnove 目录到项目根目录的相对路径。
- `repo_root`：从项目根目录到 Git 仓库的相对路径。
- `archive_root`：从 Harnove 目录到迭代归档目录的相对路径。
- `improve_root`：从 Harnove 目录到经验库的相对路径。
- `structure_root`：从 Harnove 目录到项目结构知识库的相对路径。
- `scope_policy`：必须保持 `prd_only`，所有变更只能来自 PRD。

`archive_root`、`improve_root` 和 `structure_root` 必须位于 Harnove 目录内部。重复初始化会安全补齐
新配置字段，但不会覆盖已有合法的项目配置。

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
- `improve/` 中跨迭代积累的项目经验。
- `structure/` 中持续维护的项目解读、框架和关系记录。
- 初始化生成的 `runtime/` 和 `skill/` 副本。
- 业务项目源代码、Git diff、日志和测试数据。

迭代 Harnove 自身时，仓库分析、代码修改范围、Git diff 和发行包必须排除
`harnove/iterations/`、`harnove/improve/` 与 `harnove/structure/`；运行时采集 Git 证据时也会自动应用
该排除规则。

优化 Harnove 时，应修改核心源文件。例如状态机功能修改 `scripts/harnove.py`，不要直接修改生成的 `runtime/harnove.py`；Agent 流程修改根目录 `SKILL.md`，不要直接修改生成的 `skill/` 副本。

版本号采用 `a.b.c`：仅修复或优化已有功能时增加 `c`；新增功能时增加 `b` 并将
`c` 归零；架构变更或架构优化时增加 `a` 并将 `b.c` 归零。可执行：

```powershell
python harnove/scripts/version_policy.py --previous 4.0.0 --current 4.1.0 --change-type feature
```

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
  --output releases/harnove-4.1.0
```

输出目录必须不存在或为空。打包器只复制核心白名单文件，因此未知项目文件也不会被误带入。输出中的 `package-build.json` 记录版本、配置 Schema 和所有发行文件的 SHA-256，可用于交付校验。

把新发行包放入其他项目后重新执行 `init.py` 即可升级。项目自己的配置和历史迭代归档不会被覆盖。
