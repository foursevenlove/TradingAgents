# get_industry_news "无可用数据" Bug修复报告

## 问题现象

分析任务`95aeb24c-294c-4a49-8766-f5e2218bbf28`（紫金矿业）的新闻分析师显示：
- `get_industry_news`（产业链/行业间接相关）：工具返回"无可用数据"
- 而`get_company_news`和`get_policy_news`正常返回数据

## 问题根因分析

### 1. LLM调用耗时过长

`get_industry_news`在tushare_news.py中包含多个LLM调用：
- `_llm_expand_keywords()` - 扩展行业关键词（上下游/竞争对手/技术等）
- `_llm_select_industry_news()` - 从候选新闻中精选20条
- `_llm_summarize_news()` - 为每条新闻生成200-300字摘要

这些LLM调用没有单独的timeout保护，当API响应慢时，整体耗时可能超过180秒。

**测试数据：**
| 参数 | 耗时 | 结果 |
|------|------|------|
| 直接调用（指定日期） | 6秒 | 成功返回20条 |
| 直接调用（None参数） | 121秒 | 成功返回20条 |
| route_to_vendor（None参数） | 553秒 | "No data available" |

### 2. Fallback逻辑缺陷

interface.py中第458-523行的fallback逻辑存在问题：

```python
# 原逻辑（有问题）
if "_FALLBACK_TO_AKSHARE_" in str(tushare_result):
    akshare_result = _try_vendor("akshare", ...)
    if tushare_result and akshare_result:
        return combine(tushare_result, akshare_result)
    return akshare_result  # 如果tushare有效但akshare返回空，丢弃tushare数据！
```

当tushare返回`_FALLBACK_TO_AKSHARE_`标记（表示数据可能不足）时：
1. 调用akshare fallback
2. akshare的`get_industry_news`实现是：获取全球财经快讯，用行业关键词过滤
3. 全球快讯（如"我国科研团队成功研发气固电池"）不包含"有色金属矿采选业"关键词
4. 过滤后结果为空，返回"No data available"
5. **关键问题：丢弃了tushare已经获取的20条有效行业新闻**

### 3. 环境变量加载问题

start_web_bg.sh中加载.env的方式：
```bash
export $(grep -v '^#' "$PROJECT_ROOT/.env" | grep -v '^$' | xargs)
```

这种方式可能无法正确处理某些环境变量，导致：
- DASHSCOPE_API_KEY未正确传递给LLM client
- LLM调用失败返回fallback数据

**已修复：** 在web/backend/app.py第25行已有`load_dotenv()`，确保环境变量正确加载。

## 修复方案

### 修复interface.py fallback逻辑

**文件：** `tradingagents/dataflows/interface.py`

**改动：** 第458-525行

**改进逻辑：**
```python
# 新逻辑（修复后）
if "_FALLBACK_TO_AKSHARE_" in str(tushare_result):
    tushare_content = tushare_result.replace("_FALLBACK_TO_AKSHARE_", "").strip()
    
    # 检查tushare数据是否足够（>= 5条行业新闻）
    if "# Final:" in tushare_content:
        final_count = parse_final_count(tushare_content)
        if final_count >= 5:
            return tushare_content  # 直接返回，不调用空akshare fallback
    
    # 只有当tushare数据不足时才调用akshare补充
    akshare_result = _try_vendor("akshare", ...)
    if akshare_result and "No data available" not in akshare_result:
        return combine(tushare_content, akshare_result)
    
    return tushare_content  # akshare失败时，保留tushare数据
```

**关键改进：**
1. 检查tushare返回的数据量，>=5条时直接使用
2. 只有数据不足时才尝试akshare补充
3. akshare返回"No data available"时，不丢弃tushare数据
4. 添加`import re`解析final_count

## 测试验证

### 修复后测试结果

```
测试 route_to_vendor("get_industry_news", 601899.SH, 2026-05-09, 2026-05-12)
耗时: 162.6秒
✅ 修复成功: 返回有效数据
# Final: 20 (LLM summarized)
返回: 20条行业新闻（含印度黄金进口、美国通胀、有色金属行业报告等）
```

### 验证检查清单

- [x] tushare数据足够时直接返回，不触发空akshare fallback
- [x] akshare fallback失败时不丢弃tushare数据
- [x] 返回数据包含行业相关新闻（有色金属、金银价格等）
- [x] 耗时在可接受范围（<180秒timeout）

## 其他发现

### 1. LLM调用优化建议

tushare_news.py中的LLM调用可以进一步优化：
- `_llm_expand_keywords`可缓存结果（已实现keyword_cache，TTL 30天）
- `_llm_select_industry_news`可使用分批处理（已实现BATCH_SIZE=400）
- `_llm_summarize_news`可考虑异步并行处理

### 2. akshare fallback改进建议

akshare_news.py中`get_industry_news`的实现不够智能：
- 使用全球财经快讯+行业关键词过滤，匹配率低
- 建议改进为：直接获取行业相关新闻源，或放宽关键词匹配条件

### 3. Timeout配置

当前配置：
- `tool_timeout`: 90秒（数据获取）
- `llm_timeout`: minimax=300秒, alibaba=180秒

LLM调用耗时121-162秒，在alibaba timeout范围内，但建议：
- 考虑增加新闻相关LLM调用的独立timeout
- 或在tushare_news.py中为每个LLM调用添加timeout wrapper

## 文件变更

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| interface.py | 修改 | 改进fallback逻辑，避免丢弃有效tushare数据 |

## 修复完成时间

2026-05-14

## 后续建议

1. 监控LLM调用耗时，优化prompt减少token消耗
2. 改进akshare fallback实现，提高行业新闻匹配率
3. 添加更详细的日志，记录每个LLM调用的耗时和结果