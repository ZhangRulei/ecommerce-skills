# 电商核算 Skills

包含四个独立 skill：**月度业绩核算**、**销售周报**、**剪辑人员业绩核算**和**有赞员工业绩与WPS日报**。公开仓库只发布规则、计算脚本和合成示例／测试，实际报表、员工名单、人员归属数据和凭据留在本地。

## 有赞员工业绩日报：Codex / WorkBuddy

该技能独立使用，不需要安装另外三个核算技能。流程为：**提供有赞订单CSV → 核算和对账 → WPS预览 → 写入并回读核验**。既可只领取本地结果，也可同步到个人金山文档。完整指令见 [employee-performance-wps](skills/employee-performance-wps/SKILL.md)。

### 1. 安装技能

**Codex**：将下一节的启动指令直接发给AI，让它从本仓库的 `skills/employee-performance-wps` 安装。已有skills CLI时，也可使用：

```bash
npx --yes skills add ZhangRulei/ecommerce-skills --skill employee-performance-wps --global --agent codex --yes
```

**WorkBuddy**：下载[WorkBuddy技能ZIP](packages/employee-performance-wps-workbuddy.zip?raw=true)，在“专家·技能·连接器 → 技能 → 添加技能”中上传，然后发送下一节的启动指令。界面入口以当前版本为准，参见[官方技能指南](https://www.workbuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Skills-Market)。ZIP与源码来自同一版本，额外提供WorkBuddy要求的展示元数据。

执行核算需要Python 3.10+，WPS同步需要Node.js 20.6+；两个脚本均无需第三方库。AI需能读取本地文件和执行脚本，同步还需要网络访问。只有聊天能力时不能直接完成本机脚本或WPS写入。

### 2. 复制给AI的首次启动指令

以下指令不含真实员工名单和目标文档；同事须在自己的对话或本机文件中补充这些信息。

```text
请安装并使用 employee-performance-wps 技能：
仓库：https://github.com/ZhangRulei/ecommerce-skills
技能目录：skills/employee-performance-wps
如果已通过WorkBuddy导入技能，请直接使用已安装的版本。

先阅读SKILL.md，运行技能内的合成自检，不写入云文档。
请确认我提供的订单CSV、员工代码与姓名映射，以及目标WPS链接。
只有计算需求时，先完成本地核算，不要求WPS授权。

在本机业务工作目录创建private-rules.json：
从技能config/rules.json复制规则，用我的真实名单替换employee_codes，
确认已替换全部示例姓名后，将employee_mapping_kind设为private。
使用--rules指定这份配置，不把真实名单写回公开技能目录。

按北京时间的订单创建日期核算；未指定日期时默认昨天。
排除已关闭订单，只按归属员工匹配；空白、未知或冲突归属列为待归属。
严格执行技能中的实付金额、高客单、计分和高客单订单数规则，
计分不明确时保留待核，输出汇总表、订单核对明细和待核问题。

日报采用员工纵向分块、日期横向倒序的格式：
个人账号归属业绩汇总、优质用户账号业绩、高客单业绩、
高客单分数、高客单数量、总计。优质用户账号业绩先留空。

我要求同步WPS时，协助我用本人账号完成登录、编辑权限和脚本授权，
令牌仅保存在本机，不发送到聊天或GitHub。
用同一份私有员工配置生成WPS脚本，先预览核对，
再按我的同步要求写入并回读验证；按日期和员工更新，避免重复追加。
暂不配置自动获取订单或定时任务。
```

### 3. 准备本机资料

选择一个业务工作文件夹，让AI能读取其中的原始订单。技能安装目录与业务工作文件夹可以分开：

```text
员工业绩工作目录/
├── 原始订单/订单.csv
├── private-rules.json           # 本机真实员工映射和核算规则
├── credentials.local.env        # 同步WPS时才需要，由本人在本机填写
└── out/                         # 计算结果、生成的WPS脚本及核验回执
```

订单CSV须包含：`订单号`、`订单状态`、`订单创建时间`、`全部商品名称`、`订单商品总件数`、`归属员工`、`订单实付金额`。支持UTF-8或GB18030编码及表头前后空格。相同订单号且核算字段一致时去重；字段冲突时停止核算。CSV没有目标日订单时，不据此生成零业绩。

公开的 [rules.json](skills/employee-performance-wps/config/rules.json) 仅含合成姓名。实际代码与姓名由团队另行提供，保存在本机 `private-rules.json`；不要将员工名单、原始CSV、凭据或真实结果提交到仓库。

### 4. 核算口径和日报格式

| 项目 | 规则 |
| --- | --- |
| 日期 | 北京时间的订单创建日期；未指定时默认昨天 |
| 有效订单 | 排除状态含“关闭”或“TRADE_CLOSED”的订单；不额外扣减退款 |
| 业绩 | 有效订单的订单实付金额求和，单位元 |
| 员工 | 仅按“归属员工”的字母代码匹配；空白、未知、冲突进入“待归属” |
| 高客单业绩 | 商品名称含“青春”或“玉翡”的有效订单，其整单实付求和 |
| 分数 | 青春699.99元计2分；青春1299.99元、玉翡1199.99元计4分 |
| 计分待核 | 当前CSV仅对单商品、单件且实付符合档位的高客单订单自动计分；多商品、多件或其他价格列为待核 |
| 订单数 / 高客单数量 | 分别为去重后的有效订单数 / 有效高客单订单数，不按商品件数 |
| 优质用户账号业绩 | 初始留空，后续刷新保留人工填写的值或公式 |
| 总计 | 个人账号归属业绩汇总＋优质用户账号业绩；高客单业绩已包含在个人业绩中，不重复相加 |

`Sheet1`保留日期、员工、业绩、高客单业绩、分数、订单数、高客单订单数七列明细；`业绩日报`按员工纵向分块，日期从新到旧横向排列，每人六行指标加一行间隔，总计行浅绿色。详细样式和冻结首行、前两列的操作见[日报版式](skills/employee-performance-wps/references/report-layout.md)。

不要使用添加员工、客户标签、最后添加关系、订单来源或分销员猜测“归属员工”。分数待核时仍输出金额和订单数，WPS上传器会阻止上传不确定分数。

### 5. 授权个人金山文档并同步

1. 使用本人账号打开有编辑权限的目标工作簿，保留名为`Sheet1`的工作表；也可使用所有者已授予编辑权限的共用工作簿。
2. AI根据本机`private-rules.json`生成员工名单一致的WPS脚本，在目标文档的AirScript“文档共享脚本”中安装；已有脚本时先核对版本和名单。
3. 从该脚本取得Webhook。创建个人脚本令牌需使用者本人当次明确授权，使用自己的令牌，不复制其他同事的凭据。
4. 将[空白凭据模板](skills/employee-performance-wps/config/credentials.example.env)复制到业务工作目录的`credentials.local.env`，在本机填写。不要把令牌粘贴进聊天或公开文档。
5. 先执行`preview`核对新增、更新条数，再按同步要求执行`upsert`。写入后检查`verified`和`report.verified`，并查看日报；同日同员工重算会更新已有记录。

完整操作和命令见[个人金山文档接入说明](skills/employee-performance-wps/references/wps-setup.md)。示例订单和示例员工配置均禁止写入正式工作簿。回读失败或网络中断时保留本地结果，先核查再决定是否重试，不能只凭HTTP成功报告同步完成。

### 6. 日常使用与结果领取

首次配置完成后，将当天导出的CSV放入业务工作文件夹，再向AI发送：

```text
使用 employee-performance-wps，读取我本机的private-rules.json和本次订单CSV，
计算北京时间昨天的员工业绩。先核对总金额、订单数、关闭订单、待归属及计分待核。
没有计分待核时，预览并同步到已配置的WPS工作簿，完成后回读核验。
```

如需补算，把“昨天”换成具体日期。本地`out/`包含`result.json`、`员工业绩.csv`、`订单核对明细.csv`、`待核问题.csv`；同步后另存核验回执。日报以WPS表格展示，本地CSV仍保留完整订单数指标。

**当前支持范围**：已实现“用户提供CSV → 核算 → WPS同步”。本仓库未包含自动获取有赞订单的凭据或脚本，也没有安装每天北京时间6点的定时任务。订单接口对企微群发成交员工的归因尚未验证，后续接通数据来源和执行环境后再配置定时。

## 月报、周报和剪辑业绩使用指南

### 第一步：安装三个技能（首次使用）

打开支持安装技能、能读取本地工作文件夹的 AI 工具，把下面这段话发给 AI：

> 请从 GitHub 仓库 https://github.com/ZhangRulei/ecommerce-skills 的 `skills/` 目录，把月报核算（`ecommerce-performance-accounting`）、销售周报（`ecommerce-weekly-sales`）和剪辑业绩核算（`clip-performance-accounting`）一次性安装到当前工具的用户级技能目录，并确认三个技能都能调用。

以后每次核算可直接从第二步开始。已安装旧版的同事，可先让 AI 从同一仓库更新技能。

### 第二步：在本机建文件夹，放入原始数据

新建一个工作文件夹，例如 **业绩计算**，把本次要算的月份或完整自然周的**原始导出表**放进去。有多个月份、平台、店铺或广告账户时，用子文件夹分开。例如：

```text
业绩计算/
└── 2026-10/
    ├── 抖音/
    │   ├── 示例店A/示例店A_素材分析_2026-10-01至2026-10-31.xlsx
    │   └── 示例店B/示例店B_素材分析_2026-10-01至2026-10-31.xlsx
    └── 微信小店/
        └── 示例账号/示例账号_短视频明细_20261001-20261031.xlsx
```

如果原文件名看不出归属，在**原文件名前**加上实际店铺名或账号名和下划线，例如 `示例店A_素材分析明细.xlsx`。保留原有日期、导出标识和扩展名。同一份导出只放一次。

做**剪辑业绩**时，也把已确认的人员名单、简称、各平台对应账号以及已有的人工归属表放进工作文件夹；首次使用可参考[合成映射模板](skills/clip-performance-accounting/references/attribution.example.json)。真实名单和业务数据保存在本机。

### 第三步：在 AI 工具中选中工作文件夹，发起计算

在 AI 工具里选择或打开刚才的 **业绩计算** 文件夹，让当前对话可以读取其中的文件和子文件夹。然后发下面这句话，把示例日期换成实际要算的期间：

> 使用剪辑业绩核算技能 `clip-performance-accounting`，读取当前工作文件夹中的原始导出表，计算 2026 年 10 月 1 日至 31 日的多平台剪辑人员业绩。请核对各表的统计期、平台和店铺／账户，并把最终 Excel 保存到这个工作文件夹。

做店铺月报时指定 `ecommerce-performance-accounting` 和目标月份；做销售周报时指定 `ecommerce-weekly-sales` 和自然周的起止日期。

### 第四步：回复归属问题，领取结果表

剪辑作品命中两位或更多候选人时，AI 会在对话里列出作品名称、素材 ID、金额和候选人。按编号回复即可，例如 **“1 归剪辑甲，2 归剪辑乙，3 暂缓”**。暂缓的素材保留在“待确认”里，金额计入对应渠道，待确定后再计入个人。

可先预留约 **10–20 分钟**，实际耗时随数据量和人工核对轮次变化。计算结束后，点击 AI 返回的本地 Excel 链接，或到所选工作文件夹查看结果。核对剪辑报表时，先看“已归属＋待确认”是否等于平台总额，再看各人的业绩和有效素材数。

剪辑报表的首页列顺序、人员分块、手填格和其他工作表的样式，见[汇总表格式规范](skills/clip-performance-accounting/references/workbook-format.md)。

## 可选：用命令安装

已有Node.js 22.20+和Git时：

```bash
npx --yes skills add ZhangRulei/ecommerce-skills --skill '*' --global --yes
```

这会安装本仓库四个 skill 到用户级目录，使用skills CLI的代理选择规则。需要明确指定工具时，可追加 `--agent codex` 或 `--agent claude-code`；各工具支持情况以 [skills CLI文档](https://github.com/vercel-labs/skills/blob/main/docs/commands.md) 为准。

只查看可安装列表：

```bash
npx --yes skills add ZhangRulei/ecommerce-skills --list
```

## 选择哪个skill

| Skill | 用途 | 调用例子 |
| --- | --- | --- |
| [ecommerce-performance-accounting](skills/ecommerce-performance-accounting/SKILL.md) | 月度业绩、退款备注与投放费用核算 | 使用 ecommerce-performance-accounting 计算指定月份的店铺业绩。 |
| [ecommerce-weekly-sales](skills/ecommerce-weekly-sales/SKILL.md) | 完整自然周GMV、支付、退款、退款率和实际成交 | 使用 ecommerce-weekly-sales 计算本月销售周报，跨月不截断，投放留空。 |
| [clip-performance-accounting](skills/clip-performance-accounting/SKILL.md) | 按剪辑人员汇总多平台主页及投流业绩、当期创建和有效素材 | 使用 clip-performance-accounting 从原始导出计算多平台人员月报，并与最终版逐项核对。 |
| [employee-performance-wps](skills/employee-performance-wps/SKILL.md) | 有赞每日员工业绩、高客单及分数，同步员工分块、日期倒序的WPS日报 | 使用 employee-performance-wps 核算订单CSV，并同步我授权的WPS工作簿。 |

销售周报支付与退款使用同一金额字段，完整自然周跨月不截断，月内累计单独统计；投放暂不计算。月度店铺业绩保留各渠道已确认的订单筛选、备注退款及费用规则。剪辑人员业绩按素材和账号归属统计，使用本地维护的人员映射；仓库提供[合成映射模板](skills/clip-performance-accounting/references/attribution.example.json)。

## 目录

```text
skills/
├── ecommerce-performance-accounting/
│   ├── SKILL.md
│   └── references/
├── ecommerce-weekly-sales/
│   ├── SKILL.md
│   ├── references/
│   └── scripts/
├── clip-performance-accounting/
│   ├── SKILL.md
│   ├── references/
│   └── scripts/
└── employee-performance-wps/
    ├── SKILL.md
    ├── config/
    ├── references/
    ├── examples/
    └── scripts/
```

本仓库采用 Agent Skills 目录约定。月度 skill 以规则为主；周报附标准库 Python 计算器，读取原表头 CSV 或 JSON；剪辑 skill 附单源核对和多平台总表对账脚本，读取 Excel 需要 `openpyxl`。

## 验证

周报计算器的12项合成测试：

```bash
python skills/ecommerce-weekly-sales/scripts/test_calculate_weekly.py
```

剪辑核算的合成测试（期内创建、金额门槛、多人命中和逐条确认）：

```bash
python skills/clip-performance-accounting/scripts/test_clip_accounting.py
```

员工业绩的9项Python测试、WPS明细更新与客户端模拟测试（无真实网络写入）：

```bash
python skills/employee-performance-wps/scripts/test_calculate.py
node skills/employee-performance-wps/scripts/test_wps_sync.mjs
node skills/employee-performance-wps/scripts/test_wps_client.mjs
```

使用Python 3.10+、Node.js 20.6+，无需第三方库；WPS网页版公式和样式仍需在目标文档首次接入时回读核对。公开WorkBuddy包从源码重新生成：

```bash
python tools/package_employee_performance.py
```

规则为定制业务口径，不代表平台法定结算定义。使用时提供本次材料并核实字段及日期覆盖，不能沿用历史金额。
