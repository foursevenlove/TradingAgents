"""Industry Mapper - Map themes to industries and stocks.

Maps investment themes (from ThemeExtractor) to industry classifications,
then finds related stocks in those industries.

Enhanced with LLM-based dynamic mapping when keyword matching fails.
"""

import logging
import pandas as pd
from typing import List, Dict, Optional

from tradingagents.market_data.industry_classification import (
    get_industry_list,
    get_industry_peers,
)
from tradingagents.recommendation.stock_screener import StockScreener
from tradingagents.llm_clients import create_llm_client
from tradingagents.default_config import DEFAULT_CONFIG


logger = logging.getLogger("tradingagents.web.recommendation.industry_mapper")


# Lazy-loaded LLM for dynamic industry mapping
_INDUSTRY_LLM = None


def _get_industry_llm():
    """Get LLM instance for industry mapping."""
    global _INDUSTRY_LLM
    if _INDUSTRY_LLM is None:
        try:
            client = create_llm_client(
                provider=DEFAULT_CONFIG["llm_provider"],
                model=DEFAULT_CONFIG["quick_think_llm"],
                base_url=DEFAULT_CONFIG.get("backend_url"),
            )
            _INDUSTRY_LLM = client.get_llm()
        except Exception as exc:
            logger.warning(
                "Failed to initialize industry mapping LLM; keyword fallback will be used",
                exc_info=(type(exc), exc, exc.__traceback__),
                extra={"extra_data": {"stage": "industry_mapper_llm_init"}},
            )
            _INDUSTRY_LLM = None
    return _INDUSTRY_LLM


class IndustryMapper:
    """Map themes to industries and find related stocks."""

    # Mapping of common theme keywords to Shenwan industries
    THEME_TO_INDUSTRIES = {
        "固态电池": ["电池", "有色金属", "化工原料"],
        "AI算力": ["计算机应用", "通信设备", "半导体"],
        "人工智能": ["计算机应用", "软件开发", "通信设备"],
        "大模型": ["计算机应用", "传媒", "软件开发"],
        "新能源": ["电池", "汽车整车", "电力设备"],
        "光伏": ["光伏设备", "电力设备", "化工原料"],
        "储能": ["电池", "电力设备", "电气设备"],
        "芯片": ["半导体", "电子制造", "计算机设备"],
        "半导体": ["半导体", "电子制造", "通信设备"],
        "通信": ["通信设备", "通信运营", "计算机设备"],
        "5G": ["通信设备", "通信运营", "电子制造"],
        "机器人": ["机械设备", "工业自动化", "汽车零部件"],
        "军工": ["国防军工", "航天航空", "船舶制造"],
        "医药": ["医药生物", "化学制药", "医疗器械"],
        "医疗": ["医药生物", "医疗器械", "医疗服务"],
        "白酒": ["白酒", "食品饮料"],
        "消费": ["食品饮料", "家用电器", "商贸零售"],
        "银行": ["银行", "保险", "证券"],
        "券商": ["证券", "银行", "保险"],
        "地产": ["房地产开发", "房地产服务"],
        "基建": ["建筑装饰", "工程机械", "建筑材料"],
        "电力": ["电力", "水电", "火电"],
        "煤炭": ["煤炭开采", "煤化工"],
        "石油": ["石油开采", "油服工程"],
        "有色": ["有色金属", "黄金", "稀有金属"],
        "黄金": ["黄金", "有色金属"],
        "稀土": ["稀有金属", "有色金属"],
        "钢铁": ["钢铁", "特钢"],
        "水泥": ["水泥", "建筑材料"],
        "化工": ["化工原料", "精细化工", "塑料"],
        "汽车": ["汽车整车", "汽车零部件", "新能源汽车"],
        "电动车": ["新能源汽车", "汽车整车", "电池"],
        "锂电": ["电池", "锂矿", "有色金属"],
        "光伏组件": ["光伏设备", "电力设备"],
        "风电": ["风电设备", "电力设备"],
        "氢能": ["氢能源", "化工原料"],
        "核电": ["核电设备", "电力"],
        "环保": ["环保工程", "水务", "固废处理"],
        "水务": ["水务", "环保工程"],
        "物流": ["物流", "快递", "交通运输"],
        "港口": ["港口", "航运", "交通运输"],
        "航运": ["航运", "港口", "交通运输"],
        "航空": ["航空机场", "航天航空"],
        "铁路": ["铁路运输", "交通运输"],
        "高铁": ["铁路设备", "轨道交通"],
        "地铁": ["轨道交通", "建筑工程"],
        "网游": ["游戏", "传媒", "软件开发"],
        "直播": ["传媒", "互联网", "电子商务"],
        "电商": ["电子商务", "互联网", "商贸零售"],
        "教育": ["教育", "文化传媒"],
        "影视": ["影视制作", "传媒"],
        "体育": ["体育", "文化传媒"],
        "旅游": ["旅游景点", "酒店餐饮", "交通运输"],
        "酒店": ["酒店餐饮", "旅游"],
        "餐饮": ["酒店餐饮", "食品饮料"],
        "超市": ["超市", "商贸零售"],
        "百货": ["百货", "商贸零售"],
        "服装": ["服装家纺", "纺织制造"],
        "纺织": ["纺织制造", "服装家纺"],
        "造纸": ["造纸", "包装印刷"],
        "印刷": ["包装印刷", "造纸"],
        "塑料": ["塑料", "化工原料"],
        "橡胶": ["橡胶", "化工原料"],
        "玻璃": ["玻璃", "建筑材料"],
        "陶瓷": ["陶瓷", "建筑材料"],
        "家具": ["家具", "家居用品"],
        "家电": ["家用电器", "家居用品"],
        "建材": ["建筑材料", "建筑装饰"],
        "装饰": ["建筑装饰", "家居用品"],
        "园林": ["园林工程", "建筑装饰"],
        "安防": ["安防设备", "电子制造"],
        "LED": ["LED", "光学光电子", "电子制造"],
        "显示": ["显示器件", "光学光电子"],
        "光学": ["光学光电子", "精密仪器"],
        "传感器": ["传感器", "电子制造", "半导体"],
        "物联网": ["物联网", "通信设备", "计算机应用"],
        "云计算": ["云计算", "计算机应用", "软件开发"],
        "大数据": ["大数据", "计算机应用", "软件开发"],
        "区块链": ["区块链", "金融科技"],
        "数字货币": ["数字货币", "金融科技"],
        "网络安全": ["网络安全", "计算机应用"],
        "金融科技": ["金融科技", "软件开发", "证券"],
        "保险": ["保险", "银行"],
        "信托": ["信托", "多元金融"],
        "基金": ["基金", "证券"],
        "期货": ["期货", "多元金融"],
        "创投": ["创投", "多元金融"],
        "租赁": ["租赁", "多元金融"],
        "担保": ["担保", "多元金融"],
        "典当": ["典当", "多元金融"],
    }

    def __init__(self):
        self.screener = StockScreener()

    def map_theme_to_industries_llm(
        self,
        theme_name: str,
        keywords: List[str] = None,
        max_industries: int = 5,
    ) -> List[str]:
        """Use LLM to dynamically map theme to Shenwan industries.

        Called when hardcoded keyword matching fails.
        LLM analyzes the theme semantically and returns most relevant industries.

        Args:
            theme_name: Theme name from ThemeExtractor
            keywords: Optional keywords for additional context
            max_industries: Maximum industries to return

        Returns:
            List of Shenwan industry names (level 2)
        """
        llm = _get_industry_llm()
        if llm is None:
            return []

        # Build context from keywords
        keyword_str = ""
        if keywords:
            keyword_str = f"\n关键词参考: {', '.join(keywords[:10])}"

        prompt = f"""分析以下投资主题，判断其最相关的申万行业分类（Level 2细分行业）。

主题名称: {theme_name}{keyword_str}

请从以下申万行业分类中，选出最相关的{max_industries}个行业（按相关性排序）：
半导体、通信设备、计算机应用、软件开发、电子制造、光学光电子、
电池、光伏设备、电力设备、汽车整车、汽车零部件、新能源汽车、
医药生物、化学制药、医疗器械、医疗服务、白酒、食品饮料、家用电器、
银行、证券、保险、房地产开发、建筑装饰、建筑材料、工程机械、
国防军工、航天航空、有色金属、黄金、煤炭开采、石油开采、
化工原料、精细化工、钢铁、水泥、传媒、游戏、互联网、电子商务、
物流、港口、航运、航空机场、铁路运输、水务、环保工程、电力、水电、火电、核电设备、风电设备

只返回行业名称列表，每行一个，不要序号、不要解释。
"""

        try:
            result = llm.invoke(prompt)
            content = result.content if hasattr(result, "content") else str(result)

            # Parse industries from response
            industries = []
            shenwan_industries = [
                "半导体", "通信设备", "计算机应用", "软件开发", "电子制造", "光学光电子",
                "电池", "光伏设备", "电力设备", "汽车整车", "汽车零部件", "新能源汽车",
                "医药生物", "化学制药", "医疗器械", "医疗服务", "白酒", "食品饮料", "家用电器",
                "银行", "证券", "保险", "房地产开发", "建筑装饰", "建筑材料", "工程机械",
                "国防军工", "航天航空", "有色金属", "黄金", "煤炭开采", "石油开采",
                "化工原料", "精细化工", "钢铁", "水泥", "传媒", "游戏", "互联网", "电子商务",
                "物流", "港口", "航运", "航空机场", "铁路运输", "水务", "环保工程",
                "电力", "水电", "火电", "核电设备", "风电设备",
            ]

            for line in content.split('\n'):
                line = line.strip()
                # Remove potential numbering
                if line and len(line) >= 2:
                    # Check if it matches a known Shenwan industry
                    for sw in shenwan_industries:
                        if sw in line or line in sw:
                            industries.append(sw)
                            break

            return industries[:max_industries]

        except Exception as exc:
            logger.warning(
                "Industry mapping LLM failed",
                exc_info=(type(exc), exc, exc.__traceback__),
                extra={"extra_data": {
                    "stage": "industry_mapper_llm_extract",
                    "theme_name": theme.get("name"),
                }},
            )
            return []

    def map_theme_to_industries(
        self,
        theme_name: str,
        keywords: List[str] = None,
        use_llm_fallback: bool = True,
    ) -> List[str]:
        """Map a theme to related Shenwan industry names.

        Hybrid approach:
        1. First try hardcoded keyword matching
        2. If no match and use_llm_fallback=True, use LLM dynamic mapping

        Args:
            theme_name: Theme name from ThemeExtractor
            keywords: Optional keywords for additional mapping
            use_llm_fallback: Whether to use LLM when keyword matching fails

        Returns:
            List of related industry names
        """
        industries = []

        # 1. Direct mapping from theme name
        for key, mapped in self.THEME_TO_INDUSTRIES.items():
            if key.lower() in theme_name.lower():
                industries.extend(mapped)

        # 2. Additional mapping from keywords
        if keywords:
            for kw in keywords:
                for key, mapped in self.THEME_TO_INDUSTRIES.items():
                    if key.lower() in kw.lower():
                        industries.extend(mapped)

        # Deduplicate
        industries = list(set(industries))

        # 3. LLM fallback when keyword matching yields insufficient results
        if not industries and use_llm_fallback:
            llm_industries = self.map_theme_to_industries_llm(theme_name, keywords)
            industries.extend(llm_industries)

        return industries

    def find_stocks_for_theme(
        self,
        theme: Dict,
        screened_stocks: pd.DataFrame,
        max_per_theme: int = 5,
    ) -> List[Dict]:
        """Find candidate stocks for a theme.

        Args:
            theme: Theme dict with 'name', 'keywords', 'related_industries'
            screened_stocks: DataFrame from StockScreener.screen()
            max_per_theme: Maximum stocks per theme

        Returns:
            List of stock dicts with theme, code, name, score, reason
        """
        # Get industry names for this theme
        theme_name = theme.get("name", "")
        keywords = theme.get("keywords", [])
        theme_industries = theme.get("related_industries", [])

        # Map theme to industries
        mapped_industries = self.map_theme_to_industries(theme_name, keywords)
        all_industries = list(set(mapped_industries + theme_industries))

        # Add industry column to screened stocks (only for top candidates)
        stocks_with_industry = self.screener.add_industry_to_stocks(
            screened_stocks,
            max_stocks=50,
        )

        # Filter stocks by matching industry (use keyword-based flexible match)
        if all_industries:
            matched = stocks_with_industry.copy()

            # Build keyword list from all_industries (split compound names)
            # e.g., "通信设备" -> ["通信", "设备"]
            match_keywords = set()
            for ind in all_industries:
                # Add full name
                match_keywords.add(ind.lower())
                # Split into individual keywords (common Chinese industry terms)
                common_terms = [
                    "通信", "计算机", "电子", "半导体", "电池", "汽车",
                    "电力", "医药", "化工", "机械", "军工", "银行",
                    "证券", "保险", "地产", "消费", "食品", "白酒",
                    "有色", "钢铁", "煤炭", "石油", "新能源", "光伏",
                    "储能", "风电", "核电", "氢能", "环保", "水务",
                    "物流", "港口", "航运", "航空", "铁路", "传媒",
                    "教育", "旅游", "酒店", "家电", "建材", "安防",
                    "光学", "显示", "云计算", "大数据", "物联网", "金融",
                    "设备", "制造", "运营", "服务", "应用", "开发",
                ]
                for term in common_terms:
                    if term in ind:
                        match_keywords.add(term.lower())

            def industry_match(industry_name):
                if not industry_name or industry_name == "未知":
                    return False
                ind_lower = industry_name.lower()
                for kw in match_keywords:
                    if kw in ind_lower:
                        return True
                return False

            matched = matched[matched["industry"].apply(industry_match)]
        else:
            matched = pd.DataFrame()

        # If no direct match, try fuzzy match with keywords in stock name
        if matched.empty and keywords:
            # Get all stocks from industry peers
            for industry in all_industries[:3]:  # Limit to top 3 industries
                try:
                    peers = get_industry_peers(f"000001.SZ", limit=20)  # Dummy ticker
                    # This will use industry name from theme
                    # Actually need to call with a real stock in that industry
                    # For now, skip this fallback
                except Exception as exc:
                    logger.warning(
                        "Industry peer fallback failed",
                        exc_info=(type(exc), exc, exc.__traceback__),
                        extra={"extra_data": {
                            "stage": "industry_mapper_peer_fallback",
                            "industry": industry,
                        }},
                    )
                    continue

        # Select top stocks for this theme
        top_stocks = matched.head(max_per_theme)

        # Build result list
        results = []
        for _, row in top_stocks.iterrows():
            results.append({
                "theme": theme_name,
                "code": row.get("code", ""),
                "name": row.get("name", ""),
                "price": row.get("price", 0),
                "change_pct": row.get("change_pct", 0),
                "score": row.get("score", 0),
                "industry": row.get("industry", "未知"),
                "reason": f"所属{row.get('industry', '相关')}行业，涨幅{row.get('change_pct', 0):.2f}%",
            })

        return results

    def map_all_themes(
        self,
        themes: List[Dict],
        screened_stocks: pd.DataFrame,
        max_per_theme: int = 5,
    ) -> Dict[str, List[Dict]]:
        """Map all themes to stocks.

        Args:
            themes: List of theme dicts from ThemeExtractor
            screened_stocks: DataFrame from StockScreener
            max_per_theme: Maximum stocks per theme

        Returns:
            Dict mapping theme name to list of stock dicts
        """
        result = {}
        for theme in themes:
            theme_name = theme.get("name", "")
            stocks = self.find_stocks_for_theme(
                theme,
                screened_stocks,
                max_per_theme,
            )
            result[theme_name] = stocks

        return result
