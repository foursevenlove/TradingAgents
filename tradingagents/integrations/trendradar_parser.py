"""TrendRadar新闻解析器 - 从数据库读取新闻数据"""
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional


class TrendRadarParser:
    """解析TrendRadar的SQLite数据库"""

    def __init__(self, trendradar_output_dir: str = None):
        """初始化解析器

        Args:
            trendradar_output_dir: TrendRadar输出目录，默认为~/DevSpace/code/TrendRadar/output
        """
        if trendradar_output_dir is None:
            trendradar_output_dir = str(Path.home() / "DevSpace/code/TrendRadar/output")

        self.output_dir = Path(trendradar_output_dir)
        self.news_dir = self.output_dir / "news"

    def get_latest_db(self) -> Optional[Path]:
        """获取最新的数据库文件"""
        db_files = sorted(self.news_dir.glob("*.db"), reverse=True)
        return db_files[0] if db_files else None

    def get_news(self, date: str = None, sources: List[str] = None, limit: int = 50) -> List[Dict]:
        """获取新闻数据

        Args:
            date: 日期，格式YYYY-MM-DD，默认今天
            sources: 数据源列表，如['cls-hot', 'wallstreetcn-hot']，默认全部
            limit: 最多返回条数

        Returns:
            新闻列表
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        db_path = self.news_dir / f"{date}.db"
        if not db_path.exists():
            db_path = self.get_latest_db()
            if not db_path:
                return []

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 构建查询
        query = "SELECT title, platform_id, url, first_seen_at FROM news_items"
        params = []

        if sources:
            placeholders = ','.join('?' * len(sources))
            query += f" WHERE platform_id IN ({placeholders})"
            params.extend(sources)

        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "title": row[0],
                "source": row[1],
                "url": row[2],
                "time": row[3]
            }
            for row in rows
        ]

    def get_financial_news(self, limit: int = 30) -> List[Dict]:
        """获取财经相关新闻（财联社、华尔街见闻）"""
        return self.get_news(
            sources=['cls-hot', 'wallstreetcn-hot'],
            limit=limit
        )
