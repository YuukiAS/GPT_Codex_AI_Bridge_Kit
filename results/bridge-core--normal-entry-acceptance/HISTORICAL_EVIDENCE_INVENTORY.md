# 历史原始证据盘点：不能用摘要补齐验收

本轮完成了候选实现与非 live 回归，尚未宣称十二项正式能力全部通过。下表保留已读全文、可定位但未完成核对的原始产物，以及只能在获得最终授权后产生的新证据；不能把缺项标成 PASS。

当前候选 `717d5b27bbca5d451276e6e4399ac7fc8107cf24`。AI_Skills 本地只读根为 `/overflow/htzhu/mingcheng_new/AI_Skills_Collection`；没有修改该仓库或其 branch。

| 能力 | 当前实证 | 最终仍需 |
| --- | --- | --- |
| Host | 候选绝对CLI四类transport负例与ref readback；受控本地Git FF；原受信Host validate及候选raw no_match | 处理现有机器drift的审查判断；获准后唯一consumer HTTPS FF，不能借旧CLI代执行 |
| Lite | owner未改；同candidate full tests | 冻结公开consumer的一次正式结果，待授权 |
| Review | 已全文读取 `automation/reviewed_handoff/tasks/documents-media--pdf-save-as-delivery/CURRENT.json` 与 `results/documents-media--pdf-save-as-delivery/{REVIEW_2,RESULT,FINAL_REPORT}.md`，绑定 `5c92bf4f599d378ff68444b0fa85f5d56bbbd628`、review_round2/PASS；不把历史CI失败重标 | 后续消费方仍须完整校验相应raw artifacts及first-publish证据；不得只复制PASS字段 |
| Control | owner未改；同candidate full tests | 冻结公开consumer的角色/终态原始链，待授权 |
| Persistent | 同candidate受控真实local child、生产start/supervisor及ETA/snapshot/budget回归 | 最终正式tmux/producer/status/history/真实退出链，未启动 |
| Notifier/Clear Writing | 真实installed0.5/批准双skill；machine VALID/0600/历史ready；生产budget guard故障回归 | 最终supervisor→one-shot→真实SMTP；本轮models0、SMTP0 |
| Overleaf | `overleaf.py`及模板相对formal0.11.1未改，当前full suite通过 | 0.6真实研究consumer的完整push/pull原始链尚未在当前checkout定位；指定TRACE/CAT-TRACE本地目录未发现。不用本地bare fixture冒充真实同步，不追加未授权sync |
| Visual Review | 已定位 `results/041_research_presentation_frozen_four_paper_generalization_batch/visual_review/VISUAL_REVIEW.json`，model为Terra，业务BLOCKED；owner未改、当前回归通过 | 原图、完整专业意见与身份链仍待完整消费核对；目前不声称历史复用PASS、不追加API |
| Text Review | 已全文读取055的 `text_review/TEXT_REVIEW.json`、`text_inputs.json`；实际计费0.054542美元、ACCOUNTING_VERIFIED、业务BLOCKED | 71663-byte FINAL_TERRA_PACKET.md原文与sha `86937aa8aeec281c0a4321f7f0f23139c43ce690e5edfb9ab1def9cfa9476866` 尚未就地读取；不以密文/receipt替代全文，不发第二次审核 |
| Text Transform | 真实age确定性encrypt/decrypt；count→Git预留→fake Responses→实际usage ledger同次暂存；并发/timeout/zero-billing/rerun回归 | 获准后唯一真实Actions批次；输入公钥配对与输出公钥在首次remote write前核实冻结 |
| Plugin Replay | owner未改；同candidate full tests | 冻结installed plugin的一次fresh正常入口结果，待授权 |
| 发行/机器 | 原始0.11.1closure、remote release readback；candidate wheel/模块/版本/所有runtime bytes同源，机器未升级 | 本任务只证明0.11.2候选，不授权正式分发 |

这些是验收原始材料的事实边界，不是新架构、未来产品TODO、额外授权或新的Planner/Goal。历史材料在完整原文可读、owner保持一致及当期回归适用时才可复用；未满足则最终为NO，不能悄悄换消费者、服务或样本。
