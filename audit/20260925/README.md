# 审计包说明

> **GitHub 交接说明：** 本目录是第一轮历史记录，审查基线为 `ea5e0fb`。队友复核请使用 [统一入口](../README.md#复核方式)：`python audit/review.py run --round 1 --full`。下文命令是当时的本机操作记录；不要直接在后续版本工作区重跑这些历史脚本或覆盖本目录证据。

先阅读 [工作质量与公式溯源审查报告](工作质量与公式溯源审查报告.md)，逐条数值见 [审查明细.xlsx](审查明细.xlsx)。本审计检查 `ea5e0fb`；没有修改团队原代码或结果。

## 环境

按用户要求自行建立 Conda 环境：`E:\workspace-e\set\.audit-env`，Python 3.10.20。精确 pip 依赖见 `requirements-audit.txt`。`.audit-env` 内有本地忽略文件，不纳入提交；完整复现复制目录 `reproduction/` 同样忽略。原始受跟踪文件的 SHA256 清单及最终完整性比对保存在 `evidence/input_manifest.json`、`evidence/integrity_check.json`。

在新机器的仓库根目录可按以下步骤重建。执行前应检出所审查的原始版本；审计脚本依赖现有文件结构。

```powershell
conda create --prefix .audit-env python=3.10 pip -y
& .\.audit-env\python.exe -m pip install -r audit/20260925/requirements-audit.txt
& .\.audit-env\python.exe -X utf8 audit/20260925/extract_evidence.py
& .\.audit-env\python.exe -X utf8 audit/20260925/check_results.py
& .\.audit-env\python.exe -X utf8 audit/20260925/reproduce.py
& .\.audit-env\python.exe -X utf8 audit/20260925/targeted_checks.py
& .\.audit-env\python.exe -X utf8 audit/20260925/package_report.py
```

本地实际建环境时 conda-forge 连接失败，使用本机已有缓存建立 Python 环境，再通过 pip 镜像安装依赖；未改动 base 环境。运行原主流程时脚本复制到 `reproduction/`，新生成结果只写复制目录。

## 脚本与证据

| 脚本 | 作用 | 主要输出 |
|---|---|---|
| `extract_evidence.py` | 原题数学 XML、单元格、PDF、原文件哈希提取 | 原题段号、原始数据/结果文本、PDF inventory |
| `check_results.py` | 独立数据读取、逐架次逐箱、DEM、时限、资源与链路核查 | `audit_summary.json` 和各项 CSV |
| `reproduce.py` | 在复制目录顺序执行四问 | 运行日志和 `reproduction_status.json` |
| `targeted_checks.py` | 实际投送点交叉验证、余量反例、结果比较、Q3 继承统计 | `targeted_checks.json` 和 CSV |
| `package_report.py` | 整理工作簿、冻结审计依赖、验证原文件未改 | `审查明细.xlsx`、`integrity_check.json` |

日志放在 `evidence/reproduce_*.log`，原仓库忽略规则会忽略 `.log` 文件；如转交完整日志应另行打包。`reproduction/` 含输入复制件及输出，可本地查看，不作为新的权威解答。

## 重要字段解释

- 不带新前缀的任务信息和 `feasible`、`on_time` 可能是交付原字段，不能把它们当成本审计的最终结论。
- `code_*` 调用现有程序用于检查复现一致性；独立检查另从原始附件读取参数。
- `exponent_only_energy_kwh` 只修正原题明确的航程指数，保留其他旧算法，以隔离单项影响。
- `reference_*` 使用报告明示的工程假设 `Ehor=C*d/L`、`Eup=mgh/eta` 及逐像元几何；不是已经找到原题缺失子公式。涉及能耗、SOC 和充电的该类结果仅为对照。
- `reference_duration` 用题给三阶段时间式和逐像元高度，不依赖上述能耗推导。
- `dem_underestimate_m>0` 表示原程序低估最高地面高程；小于 0 表示高估。
- `*_margin_db<0` 为相对规定门限的通信不足量；中继路线取接入和回传较差一段。
- `hard_late` 检验首批截止及医疗物资期望截止；普通物资的期望送达另作为软指标。
- Q4 按原 Q3 表计数仅用于诊断继承问题；Q3 未修复时，这不是新的最终资源配置。

## 方法边界

DEM 直线根据行列边界交点切分，逐个读取线段内部相交像元；仅触碰角点且长度为零的格子不计。通信失效使用真实交接点反例，并用全像元法、正确中心双线性法和原 LOS 方法交叉验证。有限路径采样仅能发现违规，不能单独证明连续时间全部可用。

本次审查没有重新优化方案，没有验证所有历史脚本或实飞性能，也没有证明全局最优性。论文外部来源的核验范围与访问限制以主报告为准。
