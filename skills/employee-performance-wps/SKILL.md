---
name: employee-performance-wps
description: 根据用户提供的有赞订单CSV，按归属员工代码核算每日业绩、高客单业绩、分数和订单数，并同步到WPS员工分块、日期倒序的业绩日报。适用于员工业绩日报，不用于月度店铺结算、剪辑绩效，也不推测企微群发订单归属。
---

# 有赞员工业绩与WPS日报

本技能不依赖旧聊天或原电脑。接收使用者提供的订单CSV和目标日期；WPS由使用者自己的账号单独授权。公开的 [config/rules.json](config/rules.json) 只有示例员工，真实姓名和凭据留在本机业务工作目录。

## 核算

1. 读取 [references/calculation.md](references/calculation.md)，确定输入文件和统计日期。首次使用将 `config/rules.json` 复制到业务工作目录的 `private-rules.json`，按用户给定名单替换 `employee_codes`，并设 `employee_mapping_kind` 为 `private`。勿改写公开技能内的示例配置。用户未指定日期时，默认北京时间昨天；CSV没有该日数据时，不生成“零业绩”结果。
2. 优先运行确定性计算器，不自行重写口径：
   ```sh
   python scripts/calculate.py --rules private-rules.json --input 订单.csv --date 2026-11-04 --output out
   ```
   命令路径以本技能目录为基准。若技能安装目录只读，用脚本的实际绝对路径执行，结果和凭据保存到用户授权的业务工作目录，勿写入安装目录。首次使用先运行 `python scripts/test_calculate.py`，或在不写云文档的情况下计算 `examples/demo_orders.csv` 的2026-01-02示例。
3. 检查 `out/result.json` 的控制总数、金额和待核问题。按“归属员工”匹配代码，空白、未知或冲突归属汇总到“待归属”并保留原因。不得改用添加员工、标签、最后添加关系或分销员来猜测归属。
4. 未定义的计分情况保留为待核，不把未知分数伪装为0；金额和订单数仍正常统计。当前CSV计分仅能验证单商品、单件、整单实付符合已确认档位的情况。混合购买、多件或其他价格需要补充商品级数据/用户口径。

## WPS同步

仅当使用者要求同步且指定目标文档时，读取 [references/wps-setup.md](references/wps-setup.md)。先用 `scripts/prepare_wps_script.py --rules private-rules.json --output out/wps-performance-sync.js` 生成含本机名单的脚本，再在WPS的“文档共享脚本”中安装生成的文件。复用已有脚本时也须核对名单一致。使用本人脚本令牌与该脚本Webhook，本技能包没有预置凭据。

先预览，核对新增/更新条数，再按已授权范围写入：

```sh
node --env-file=credentials.local.env scripts/wps_push.mjs --input out/result.json --mode preview
node --env-file=credentials.local.env scripts/wps_push.mjs --input out/result.json --mode upsert
```

写入后检查 `verified` 和 `report.verified`，并查看 `业绩日报`。按日期和员工更新，不重复追加；回读失败不能报告同步成功。脚本保存底层明细在 `Sheet1`，订单数保留在F列，高客单订单数在G列。日报采用 [references/report-layout.md](references/report-layout.md) 的格式。

## 交付与范围

向用户说明统计日期、排除关闭订单数、业绩总金额、高客单总金额/单数、待归属与待核数量；输出结果文件，按需要附目标WPS链接。不要把脚本令牌写进聊天、结果文件、技能包或截图。

“核算和WPS写入”与“每天定时获取订单”是两个环节。订单接口的企微群发成交归因尚未验证，不宣称已接通；未获得新的定时任务要求时，不自行建立自动任务。

使用者若只有聊天能力、没有本地文件/脚本/网络工具，先给出核算结果文件，并准确说明哪一步需要执行环境。不要把生成一段代码当成已写入WPS。
