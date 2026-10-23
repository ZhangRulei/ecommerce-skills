# 电商核算 Skills

包含两个独立 skill：**月度业绩核算**和**销售周报**。公开仓库，只发布规则、计算脚本和合成测试，不包含订单、客户数据、密码或实际报表。

## 给AI一句话安装

在支持Agent Skills安装、且能访问本地文件的AI工具中发送：

> 请从 https://github.com/ZhangRulei/ecommerce-skills 安装 ecommerce-performance-accounting 和 ecommerce-weekly-sales 两个 skill，到当前工具的用户级技能目录。

支持GitHub skill安装的助手可直接读取此仓库的 `skills/` 目录。网页版聊天工具若没有技能安装功能，需要改用其支持的导入方式，不能只靠对话完成安装。

## 一条命令安装

已有Node.js 22.20+和Git时：

```bash
npx --yes skills add ZhangRulei/ecommerce-skills --skill '*' --global --yes
```

这会安装本仓库两个 skill 到用户级目录，使用skills CLI的代理选择规则。需要明确指定工具时，可追加 `--agent codex` 或 `--agent claude-code`；各工具支持情况以 [skills CLI文档](https://github.com/vercel-labs/skills/blob/main/docs/commands.md) 为准。

只查看可安装列表：

```bash
npx --yes skills add ZhangRulei/ecommerce-skills --list
```

## 选择哪个skill

| Skill | 用途 | 调用例子 |
| --- | --- | --- |
| [ecommerce-performance-accounting](skills/ecommerce-performance-accounting/SKILL.md) | 月度业绩、退款备注与投放费用核算 | 使用 ecommerce-performance-accounting 计算指定月份的店铺业绩。 |
| [ecommerce-weekly-sales](skills/ecommerce-weekly-sales/SKILL.md) | 完整自然周GMV、支付、退款、退款率和实际成交 | 使用 ecommerce-weekly-sales 计算本月销售周报，跨月不截断，投放留空。 |

两套业务口径不同，不要混用。销售周报支付与退款使用同一金额字段，完整自然周跨月不截断，月内累计单独统计；投放暂不计算。月度业绩保留各渠道已确认的订单筛选、备注退款及费用规则。

## 目录

```text
skills/
├── ecommerce-performance-accounting/
│   ├── SKILL.md
│   └── references/
└── ecommerce-weekly-sales/
    ├── SKILL.md
    ├── references/
    └── scripts/
```

本仓库采用Agent Skills目录约定，不依赖Codex专用的agents配置。月度 skill 以规则为主；周报附标准库Python计算器，读取原表头CSV或JSON。Excel读取、解密及表格制作由所用AI工具提供能力。

## 验证

周报计算器的12项合成测试：

```bash
python skills/ecommerce-weekly-sales/scripts/test_calculate_weekly.py
```

规则为定制业务口径，不代表平台法定结算定义。使用时提供本次材料并核实字段及日期覆盖，不能沿用历史金额。
