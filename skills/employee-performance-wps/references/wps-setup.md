# 个人金山文档首次接入

使用者本人需要拥有目标工作簿编辑权限。可以使用自己的空白工作簿，保留一个名为Sheet1的工作表；也可以使用被文件所有者明确授予编辑权限的共用工作簿。不要复制原操作者电脑中的令牌或配置。

1. 打开目标工作簿，找到“效率 → 高级开发 → AirScript脚本编辑器”。菜单随版本有差异，以实际页面为准。若目标文档没有脚本能力，先确认表格类型及账号功能，不假设一定可调用。
2. 先用本机 `private-rules.json` 运行下方生成命令，得到含实际员工名单的 `out/wps-performance-sync.js`。检查是否已有符合本流程且本人可执行的“员工业绩同步”文档共享脚本；名单一致时可复用它的Webhook。没有时，在“文档共享脚本”下新建并粘贴生成的文件；勿粘贴技能内含示例名单的模板。不要放在“我的脚本”下：官方当前只开放文档共享脚本的Webhook。
3. 首先在编辑器直接运行。默认preview只检查，不写数据。空白Sheet1应显示existingRecords=0、headerReady=false；非空表必须有准确六列表头，否则会停止保护数据。
4. 在该脚本的“更多”菜单复制“脚本webhook”。同步执行地址应为https://www.kdocs.cn/api/v3/ide/file/文件标识/script/脚本标识/sync_task。
5. 由使用者本人确认创建个人脚本令牌，必要时本人完成实名认证。令牌是账号级凭据，可配合相应Webhook读写有权限的文件。创建持久访问凭据前应取得使用者当次明确授权；本技能和原操作者的授权不能代替同事自己的授权。
6. 把config/credentials.example.env复制到用户授权的可写业务工作目录，命名credentials.local.env。在本地填写目标文档链接、Webhook、令牌，不贴进聊天。技能安装目录可能只读，不往其中保存结果或凭据。文件夹应由本人账号管理，不与技能包一起转发。该文件已列入.gitignore；仍要避免手工压缩时把它打包。
7. 先preview，再根据使用者的同步要求upsert。正式同步器拒绝将虚构示例或未配置实际员工的结果写入云表；请提供真实订单CSV、目标日期和本机员工配置。

## 执行命令

需要Python 3.10+与Node.js 20.6+，脚本无额外第三方依赖。以下命令中的脚本路径相对技能目录，私有配置、输入和输出路径相对业务工作目录；两者不同时使用绝对路径。修改本机名单后重新生成WPS脚本，核算器和云脚本须使用同一名单。

```sh
python scripts/prepare_wps_script.py --rules private-rules.json --output out/wps-performance-sync.js
python scripts/calculate.py --rules private-rules.json --input 订单.csv --date 2026-11-04 --output out
node --env-file=credentials.local.env scripts/wps_push.mjs --input out/result.json --mode preview
node --env-file=credentials.local.env scripts/wps_push.mjs --input out/result.json --mode upsert
node --env-file=credentials.local.env scripts/wps_push.mjs --input out/result.json --mode inspect
```

mode为rebuild时，只刷新横向日报，不重写底层明细。inspect返回读取结果，便于核对，不要将含真实业绩的读取文件随技能转发。写入成功需同时确认verified和report.verified，不能只看HTTP成功。

如果网络或权限失败，保留本地核算结果并说明失败位置。没有读到数据不能按0业绩上传；响应不明确时先inspect，再决定是否重试。

## 定时执行

本包没有安装定时任务，也没有自动抓取有赞订单的凭据或脚本。用户明确要求定时后，再在对应AI的官方定时功能或已授权的常驻执行环境中配置。需同时确认每天CSV如何到达、北京时间6点执行、缺文件时如何通知、以及同日重算更新而非重复新增。

## 官方资料

- AirScript脚本令牌：https://airsheet.wps.cn/docs/apitoken/intro.html
- AirScript执行接口：https://airsheet.wps.cn/docs/apitoken/api.html
- WorkBuddy上传技能：https://www.workbuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Skills-Market
- WorkBuddy技能包结构：https://open.workbuddy.cn/docs/skill
- Codex本地技能：https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills
