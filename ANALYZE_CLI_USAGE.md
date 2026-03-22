# analyze.py - 非交互式命令行工具使用说明

## 概述

`analyze.py` 是 TradingAgents 的非交互式命令行工具，可以通过命令行参数直接运行股票分析，无需交互式输入。

这个工具特别适合：
- **自动化脚本**：在脚本中批量分析多只股票
- **定时任务**：通过 cron 或其他调度工具定期运行
- **OpenClaw 集成**：作为 OpenClaw skill 的后端执行工具
- **CI/CD 集成**：在持续集成流程中运行分析

## 基本用法

### 最简单的用法（使用默认配置）

```bash
python analyze.py --ticker 000001
```

这将使用以下默认配置：
- 分析日期：今天
- 研究深度：2
- 分析师：全部（market, social, news, fundamentals）
- LLM 提供商：minimax
- 模型：自动选择（MiniMax-M2.5 和 MiniMax-M2.7）

### 指定日期

```bash
python analyze.py --ticker 000001 --date 2026-03-22
```

### 指定研究深度

```bash
# 快速分析（深度1）
python analyze.py --ticker 000001.SZ --depth 1

# 深度分析（深度5）
python analyze.py --ticker 000001.SZ --depth 5
```

研究深度说明：
- **1**: 快速分析，最少的辩论轮次
- **2**: 标准分析（默认）
- **3**: 深入分析
- **4**: 详细分析
- **5**: 最深入分析，最多的辩论轮次

### 选择特定分析师

```bash
# 只使用市场和新闻分析师
python analyze.py --ticker 000001.SZ --analysts market,news

# 只使用基本面分析师
python analyze.py --ticker 000001.SZ --analysts fundamentals
```

可选的分析师：
- `market`: 市场技术分析师
- `social`: 社交媒体情绪分析师
- `news`: 新闻分析师
- `fundamentals`: 基本面分析师

### 静默模式

```bash
# 静默模式，只输出最终报告路径
python analyze.py --ticker 000001 --quiet
```

静默模式适合在脚本中使用，可以直接获取报告路径：

```bash
REPORT_PATH=$(python analyze.py --ticker 000001.SZ --quiet)
echo "报告已生成: $REPORT_PATH"
```

## 完整参数列表

```
--ticker        股票代码（必需）
                示例: 000001.SZ, 600000.SH

--date          分析日期（可选）
                格式: YYYY-MM-DD
                默认: 今天

--depth         研究深度（可选）
                范围: 1-5
                默认: 2

--analysts      分析师列表（可选）
                格式: 逗号分隔
                可选: market, social, news, fundamentals
                默认: 全部

--provider      LLM 提供商（可选）
                可选: minimax
                默认: minimax

--shallow       快速思考模型（可选）
                默认: 根据 provider 自动选择

--deep          深度思考模型（可选）
                默认: 根据 provider 自动选择

--quiet         静默模式（可选）
                只输出最终报告路径

--help          显示帮助信息
```

## 输出结果

### 报告位置

分析完成后，报告会保存在以下位置：

```
results/
└── {ticker}/
    └── {date}/
        ├── {ticker}_{date}_final_report.md  # 最终综合报告
        └── reports/                          # 各个分析师的详细报告
            ├── market_report.md
            ├── news_report.md
            ├── fundamentals_report.md
            ├── sentiment_report.md
            ├── research_team_decision.md
            ├── trader_plan.md
            └── final_decision.md
```

### 示例输出

```
============================================================
TradingAgents 股票分析
============================================================
股票代码: 000001.SZ
分析日期: 2026-03-22
研究深度: 2
分析师: market, social, news, fundamentals
LLM提供商: minimax
快速模型: MiniMax-M2.5
深度模型: MiniMax-M2.7
============================================================

正在初始化分析图...
结果目录: results/000001.SZ/2026-03-22

开始分析...

[分析过程...]

============================================================
分析完成！
============================================================
最终报告: results/000001.SZ/2026-03-22/000001.SZ_2026-03-22_final_report.md
详细报告: results/000001.SZ/2026-03-22/reports
============================================================
```

## 高级用法示例

### 批量分析多只股票

```bash
#!/bin/bash
# batch_analyze.sh

STOCKS=("000001.SZ" "600000.SH" "000002.SZ")
DATE="2026-03-22"

for stock in "${STOCKS[@]}"; do
    echo "正在分析 $stock..."
    python analyze.py --ticker "$stock" --date "$DATE" --depth 2
    echo "完成 $stock"
    echo "---"
done
```

### 在 Python 脚本中调用

```python
import subprocess
import json

def analyze_stock(ticker, date=None):
    """调用 analyze.py 分析股票"""
    cmd = ["python", "analyze.py", "--ticker", ticker, "--quiet"]
    if date:
        cmd.extend(["--date", date])

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        report_path = result.stdout.strip()
        print(f"分析成功: {report_path}")
        return report_path
    else:
        print(f"分析失败: {result.stderr}")
        return None

# 使用示例
report = analyze_stock("000001", "2026-03-22")
```

## 错误处理

### 常见错误

1. **无效的股票代码**
   ```
   错误: 无效的股票代码: INVALID
   ```
   解决：检查股票代码格式

2. **无效的日期格式**
   ```
   错误: 无效的日期格式: 2026/03/22，应为 YYYY-MM-DD
   ```
   解决：使用正确的日期格式 YYYY-MM-DD

3. **API 密钥未配置**
   ```
   错误: 未找到 MINIMAX_API_KEY 环境变量
   ```
   解决：在 .env 文件中配置相应的 API 密钥

4. **分析失败**
   ```
   错误: 分析失败
   错误信息: [具体错误信息]
   ```
   解决：查看错误信息，检查网络连接、API 配额等

## 性能优化建议

1. **选择合适的研究深度**
   - 快速分析使用 `--depth 1`
   - 日常分析使用 `--depth 2`（默认）
   - 重要决策使用 `--depth 4-5`

2. **选择必要的分析师**
   - 如果只需要技术分析，使用 `--analysts market`
   - 如果只需要基本面，使用 `--analysts fundamentals`
   - 完整分析使用全部分析师

3. **使用静默模式**
   - 在脚本中使用 `--quiet` 减少输出
   - 提高批量处理效率

4. **并行处理**
   - 使用 GNU parallel 或 xargs 并行分析多只股票
   ```bash
   cat stocks.txt | xargs -P 4 -I {} python analyze.py --ticker {} --quiet
   ```

## 与交互式 CLI 的对比

| 特性 | analyze.py | python -m cli.main |
|------|-----------|-------------------|
| 交互方式 | 命令行参数 | 交互式问答 |
| 适用场景 | 自动化、脚本 | 手动分析 |
| 输出方式 | 简洁/静默 | 丰富的实时显示 |
| 易用性 | 需要记住参数 | 引导式操作 |
| 集成性 | 易于集成 | 不适合集成 |

## 故障排查

### 查看详细日志

如果分析失败，可以查看详细的错误信息：

```bash
python analyze.py --ticker 000001 2>&1 | tee analysis.log
```

### 测试 API 连接

```bash
# 测试 MiniMax API
python -c "from tradingagents.llm_clients.factory import create_llm_client; client = create_llm_client('minimax'); print('连接成功')"
```

### 检查依赖

```bash
pip install -r requirements.txt
```

## 总结

`analyze.py` 提供了一个简洁、灵活的非交互式接口，特别适合：
- ✅ OpenClaw skill 集成
- ✅ 自动化脚本
- ✅ 定时任务
- ✅ 批量处理
- ✅ CI/CD 集成

对于日常手动分析，仍然推荐使用交互式 CLI：`python -m cli.main`
