# Harnove

Harnove 是一个面向代码研发的迭代 Harness。它使用隔离子 Agent、人工审核闸门、
独立 Git 分支和可追溯归档，把自然语言需求或 PRD 推进为代码实现。

Harnove 提供两种互相独立的工作流：

- **专家模式（expert，默认）**：需求澄清 → 技术方案 → 代码方案 → 测试方案 →
  代码实现 → 测试执行 → 总结。
- **敏捷模式（agile）**：需求澄清 → 代码方案 → 代码实现 → 总结。

两种模式都遵守 `custom/user.md` 和 `custom/self.md`，文档必须由用户明确审核批准，
代码实现前都会创建并切换独立分支，总结阶段都会更新 `structure/`、`improve/` 和
可复用经验。

## 环境要求

- Python 3.10 或更高版本。
- 目标项目是 Git 仓库。
- 使用支持子 Agent 的 Codex、Claude Code 或 Cursor。
- 准备一份本地 PRD，或直接提供自然语言需求。

GitHub CLI、Homebrew 和 Node.js 不是安装依赖。若当前平台无法创建子 Agent，
Harnove 会停止，不会降级为不隔离执行。

## 1. 下载并放入项目

从 [Harnove GitHub 仓库](https://github.com/jerryrain-nova/harnove) 选择
`Code → Download ZIP`，解压后把目录复制到目标项目根目录并命名为 `harnove`：

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

确保最终路径是 `your-project/harnove/init.py`，不要形成
`harnove/harnove-main/init.py` 双层目录。

## 2. 初始化

macOS / Linux：

```bash
python3 harnove/init.py --project .
```

Windows PowerShell：

```powershell
python .\harnove\init.py --project .
```

如果 Harnove 位于项目之外：

```bash
python3 /path/to/harnove/init.py --project /path/to/your-project
```

此时 Harnove 会安装到目标项目的 `.harnove/`。初始化会安装 Codex、Claude Code
和 Cursor 入口，并创建运行时、配置、迭代归档、项目结构和经验目录。初始化完成后，
重新打开目标项目工作区并新建 Agent 会话，让平台发现 Skill。

## 3. 选择模式并启动迭代

启动前，Agent 必须：

1. 根据需求建议一个适合分支名的迭代名称。
2. 询问使用专家模式还是敏捷模式。
3. 等用户确认名称和模式后再初始化。

未指定模式时使用专家模式，以兼容已有使用方式。

### 专家模式

适合复杂需求、跨模块改动、需要正式技术设计或完整测试证据的迭代。

Codex：

```text
使用 $harnove 以专家模式启动 ITER-20260724-001。
需求名称：order-export。
需求：在订单列表增加批量导出；格式和数量上限还没有确定。
```

Claude Code / Cursor：

```text
/harnove 以专家模式启动 ITER-20260724-001，需求名称 order-export：
在订单列表增加批量导出；格式和数量上限还没有确定。
```

底层命令使用：

```bash
python3 harnove/runtime/harnove.py init \
  --mode expert \
  --iteration-id ITER-20260724-001 \
  --iteration-name order-batch-export \
  --requirement order-export \
  --description "在订单列表增加批量导出"
```

专家模式完整流程：

```text
需求澄清与候选 PRD
→ 人工批准
→ 技术方案
→ 人工批准
→ 代码方案
→ 人工批准
→ 测试方案
→ 人工批准
→ 新分支代码实现
→ 测试执行
→ 总结与经验沉淀
```

符合小改动条件时，专家模式可以把代码方案与测试方案合并为一份文档、一次人工
审核；这是专家模式内部优化，不会改变敏捷模式。

### 敏捷模式

适合边界清晰、希望快速实现且不需要独立技术方案和测试阶段的需求。

Codex：

```text
使用 $harnove 以敏捷模式启动 ITER-20260724-002。
需求名称：order-validation。
需求：沿用现有错误提示，调整订单模块中的局部校验逻辑。
```

已有 PRD 时：

```text
使用 $harnove 以敏捷模式，基于 docs/prd/order-validation.md
启动 ITER-20260724-002。
```

底层命令：

```bash
python3 harnove/runtime/harnove.py init \
  --mode agile \
  --iteration-id ITER-20260724-002 \
  --iteration-name order-validation \
  --requirement order-validation \
  --prd docs/prd/order-validation.md
```

敏捷模式流程：

```text
需求澄清
→ 用户一次性明确确认边界/模糊点已澄清完毕并批准完整需求基线
→ 代码改动方案（只设计，不修改代码）
→ 人工批准
→ 创建并切换新分支
→ 代码实现
→ 总结、structure/improve 更新及代码改动点输出
```

敏捷模式不会创建技术方案、独立测试方案或测试执行阶段。代码方案被驳回时，
主 Agent 先结合反馈说明哪些章节和改动点会变化；只有用户批准变更影响说明后，
才派发全新子 Agent 生成下一版本。敏捷模式不会复用或改变专家模式的阶段规则。

READY 需求文档只设置一次正式人工审核，不额外创建“澄清完成”闸门；批准原文必须
同时表达澄清完毕和当前完整需求基线获批。

## 4. 人工审核

候选需求文档以及当前模式中的设计文档都必须由用户明确批准。校验通过、子 Agent
完成、用户沉默或 Agent 自行判断合格，都不算批准。

- 文档无误：明确回复“批准当前完整文档”。
- 文档需修改：直接给出反馈。
- 主 Agent 会先展示受影响章节、变化原因和不变边界。
- 用户批准变化范围后才生成新版本；新版本仍需重新审核。

底层批准命令必须逐字保存用户原话：

```bash
python3 harnove/runtime/harnove.py review \
  --archive <迭代目录> \
  --decision approve \
  --reviewer "<审核人>" \
  --human-confirmation "<用户明确批准原文>"
```

历史版本不会被覆盖。v002 及后续版本会包含精简的“版本演进摘要”。

## 5. 分支、超时与总结

代码实现前会创建并切换独立分支，默认格式：

```text
tmp/{迭代名称}-{实施轮次}
```

用户提供了分支规则时优先使用用户规则。专家模式测试失败后，会询问在当前实现分支
修复还是创建新分支；敏捷模式没有测试执行阶段。

每个子 Agent 工作单包含明确的到期时间。非简单项目会放宽关键阶段阈值；真实超时
会跨迭代学习：第一次增加 50%，第二次增加 30%，第三次及以后每次增加 10%。
普通失败、崩溃或人工取消不会扩大超时阈值。

两种模式的总结都会：

- 检查完成后的当前仓库。
- 更新 `structure/` 的功能模块、代码框架和结构关系抽象。
- 写入 `improve/` 可复用经验。
- 把用户反馈提炼到 `custom/self.md`。
- 记录实际 Git 证据。

敏捷模式总结还必须向用户展示实际代码改动点。

## 6. 查看状态

通常直接询问 Agent“当前 Harnove 迭代状态”即可，也可以执行：

```bash
python3 harnove/runtime/harnove.py status \
  --archive harnove/iterations/<迭代目录>
```

Windows：

```powershell
.\harnove\run.ps1 status --archive .\harnove\iterations\<迭代目录>
```

状态输出会显示 `workflow_mode`、当前阶段、人工闸门、分支和超时配置。

## 7. 数据目录

```text
harnove/
├─ config.json          项目配置
├─ timeout-policy.json  跨迭代自适应超时经验
├─ iterations/          文档、审核和执行证据
├─ improve/             跨迭代复用经验
├─ structure/           完成后的项目结构抽象
└─ custom/
   ├─ user.md           项目长期约束和偏好
   └─ self.md           从历史反馈中提炼的经验
```

专家模式会使用全部阶段目录；敏捷模式只在需求输入、代码方案、实现和总结目录中产生
阶段产物。`state.json` 是流程状态的唯一权威来源，不得人工修改。

## 8. 升级

用新版发行目录替换核心文件后重新执行：

```bash
python3 harnove/init.py --project .
```

初始化不会删除项目配置、历史迭代、`improve/`、`structure/`、`custom/` 或
`timeout-policy.json`。检测到人工修改的托管文件时会停止；确认覆盖时使用：

```bash
python3 harnove/init.py --project . --force-managed-files
```

## 进一步阅读

- [完整使用手册](USAGE.md)
- [Agent 工作流约束](SKILL.md)
- [文档与审核产物契约](references/artifact-contracts.md)
