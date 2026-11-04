# 电商核算 Skills

包含三个独立 skill：**月度业绩核算**、**销售周报**和**剪辑人员业绩核算**。公开仓库只发布规则、计算脚本和合成示例／测试，实际报表和人员归属数据留在本地。

## 同事使用指南

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

这会安装本仓库三个 skill 到用户级目录，使用skills CLI的代理选择规则。需要明确指定工具时，可追加 `--agent codex` 或 `--agent claude-code`；各工具支持情况以 [skills CLI文档](https://github.com/vercel-labs/skills/blob/main/docs/commands.md) 为准。

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
└── clip-performance-accounting/
    ├── SKILL.md
    ├── references/
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

规则为定制业务口径，不代表平台法定结算定义。使用时提供本次材料并核实字段及日期覆盖，不能沿用历史金额。
