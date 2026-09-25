# 最新提交补充审计包

> **GitHub 交接说明：** 本目录是第二轮历史记录，审查基线为 `e94e1cc`。队友复核请使用 [统一入口](../README.md#复核方式)：`python audit/review.py run --round 2 --full`。下文命令保留为当时操作记录；统一入口会在独立副本中复核，无需运行历史 `prepare.py` 或 `package_update.py`，也不会改写已发布证据。

本目录记录 `ea5e0fb → e94e1cc` 更新及补充评估。审查始于2026-09-25，完成于2026-09-26；目录日期沿用开始日期。原 `audit/20260925/` 没有被覆盖。

- [补充评估报告](最新提交补充评估报告.md)
- [检查明细工作簿](补充评估明细.xlsx)

## 环境与执行

使用用户要求的独立 Conda 环境 `.audit-env`，本轮为 CP-SAT 反例新增 OR-Tools 9.10.4067，完整依赖见 `requirements-audit.txt`。未修改原有求解代码。最新代码复制到 `reproduction/`，所有求解输出仅写该复制目录。

从仓库根目录运行，先确认当前为所审查的提交：

```powershell
& .\.audit-env\python.exe -X utf8 audit/20260925_update/prepare.py
& .\.audit-env\python.exe -X utf8 audit/20260925_update/extract_evidence.py
& .\.audit-env\python.exe -X utf8 audit/20260925_update/check_results.py
& .\.audit-env\python.exe -X utf8 audit/20260925_update/reproduce_update.py
& .\.audit-env\python.exe -X utf8 audit/20260925_update/run_extras.py
& .\.audit-env\python.exe -X utf8 audit/20260925_update/targeted_checks.py
& .\.audit-env\python.exe -X utf8 audit/20260925_update/check_additions.py
& .\.audit-env\python.exe -X utf8 audit/20260925_update/package_update.py
```

`prepare.py` 从上一轮复制审计检查器，保留同一独立方法，并自动将 `targeted_checks.py` 的复现比较目录适配为新版交付位置 `reproduction/解题-gpt/结果`。该适配只涉及审计器，不涉及求解程序。

## 关键证据

| 文件 | 内容 |
|---|---|
| `pull_preflight.json` | 拉取前/远程提交、路径冲突检查、原审计109文件哈希 |
| `remote_changes.txt` | 完整变更路径及重命名记录 |
| `evidence/post_pull_manifest.json` | 更新后的408个受跟踪文件初始哈希 |
| `evidence/integrity_check.json` | 原审计保留、新版本未改的结束时验证 |
| `evidence/audit_summary.json` | 正式工作簿逐架次、逐箱、资源、通信、中继续航和Q4时限 |
| `evidence/targeted_checks.json` | 真实投送点交叉验证、余量敏感性、9张不一致工作表、Q4继承对照 |
| `evidence/additions_summary.json` | ALNS候选、重跑Q3、新能耗函数、NSGA航段重复、CP-SAT截断反例 |
| `evidence/new_papers/` | 三份新增Word正文/公式文本及完整文档XML |
| `evidence/reproduction_status.json` | 新交付入口的逐个运行状态 |
| `evidence/extra_run_status.json` | 根入口重跑、ALNS250次及团队校验器状态 |

运行日志为 `evidence/*.log`，受原仓库 `.gitignore` 忽略，本地存在；复制环境也通过目录内 `.gitignore` 忽略。需要交接全部日志时可单独打包。

## 必须保留的解释边界

- 原表的 `feasible` / `on_time` 不代表本审计认可；独立检查列另外给出。
- `reference_*` 是工程假设对照，不是原题唯一答案。Q3超载行超出题给航程定义域，不能用其外推能耗作为合规结果。
- ALNS主要指标可复现，但具体任务顺序和资源分配表不完全复现；结果文件里的浮点误差与实际排列差异已区分。
- CP-SAT的1.09分钟案例是小型合成反例，不是官方货箱结果。
- 新 NSGA-II 大规模全搜索未执行：结果表为空，函数级实际反例已证明关键建模缺陷。
- 本次根Q2首次运行缺复制目录的输出文件夹，补齐空目录后成功，不把该问题归咎于原仓库。

五篇新增算法文献的原始链接及来源核验边界见报告。上一轮14篇本地PDF内容未改变，沿用历史核验结论。
