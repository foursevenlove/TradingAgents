"""Agent执行日志记录器"""
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


class AgentLogger:
    """记录agent执行过程的日志"""

    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.current_session = None
        self.session_data = {
            "session_id": None,
            "start_time": None,
            "ticker": None,
            "date_range": None,
            "agents": []
        }

    def start_session(self, ticker: str, start_date: str, end_date: str):
        """开始新的分析会话"""
        self.current_session = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_data = {
            "session_id": self.current_session,
            "start_time": datetime.now().isoformat(),
            "ticker": ticker,
            "date_range": {"start": start_date, "end": end_date},
            "agents": []
        }
        # 立即创建日志文件
        self._save_incremental()

    def log_agent_start(self, agent_name: str):
        """记录agent开始执行"""
        agent_log = {
            "agent_name": agent_name,
            "start_time": datetime.now().isoformat(),
            "tool_calls": [],
            "thinking": [],
            "output": None,
            "end_time": None
        }
        self.session_data["agents"].append(agent_log)
        self._save_incremental()
        return len(self.session_data["agents"]) - 1

    def log_tool_call(self, agent_idx: int, tool_name: str, args: Dict[str, Any], result: Optional[str] = None):
        """记录工具调用"""
        if agent_idx < len(self.session_data["agents"]):
            tool_log = {
                "tool": tool_name,
                "args": args,
                "time": datetime.now().isoformat(),
                "result_preview": result[:200] if result else None
            }
            self.session_data["agents"][agent_idx]["tool_calls"].append(tool_log)
            self._save_incremental()

    def log_thinking(self, agent_idx: int, content: str):
        """记录agent思考过程"""
        if agent_idx < len(self.session_data["agents"]):
            self.session_data["agents"][agent_idx]["thinking"].append({
                "time": datetime.now().isoformat(),
                "content": content[:500]  # 只保存前500字符
            })

    def log_agent_end(self, agent_idx: int, output: str):
        """记录agent执行结束"""
        if agent_idx < len(self.session_data["agents"]):
            self.session_data["agents"][agent_idx]["end_time"] = datetime.now().isoformat()
            self.session_data["agents"][agent_idx]["output"] = output
            self._save_incremental()

    def _save_incremental(self):
        """实时增量保存日志"""
        if self.current_session:
            log_file = self.log_dir / f"session_{self.current_session}.json"
            with open(log_file, "w", encoding="utf-8") as f:
                json.dump(self.session_data, f, ensure_ascii=False, indent=2)

            txt_file = self.log_dir / f"session_{self.current_session}.txt"
            self._save_readable_log(txt_file)

    def save_session(self):
        """保存会话日志到文件（最终调用）"""
        self._save_incremental()
        if self.current_session:
            return self.log_dir / f"session_{self.current_session}.json"

    def _save_readable_log(self, txt_file: Path):
        """生成可读的文本日志"""
        with open(txt_file, "w", encoding="utf-8") as f:
            f.write(f"=== 交易分析会话日志 ===\n")
            f.write(f"会话ID: {self.session_data['session_id']}\n")
            f.write(f"开始时间: {self.session_data['start_time']}\n")
            f.write(f"股票代码: {self.session_data['ticker']}\n")
            f.write(f"日期范围: {self.session_data['date_range']['start']} 至 {self.session_data['date_range']['end']}\n")
            f.write(f"\n{'='*60}\n\n")

            for i, agent in enumerate(self.session_data["agents"], 1):
                f.write(f"[{i}] {agent['agent_name']}\n")
                f.write(f"开始: {agent['start_time']}\n")

                if agent["tool_calls"]:
                    f.write(f"\n工具调用 ({len(agent['tool_calls'])}次):\n")
                    for j, tool in enumerate(agent["tool_calls"], 1):
                        f.write(f"  {j}. {tool['tool']}({', '.join(f'{k}={v}' for k, v in tool['args'].items())})\n")
                        f.write(f"     时间: {tool['time']}\n")

                if agent["thinking"]:
                    f.write(f"\n思考过程 ({len(agent['thinking'])}条):\n")
                    for j, think in enumerate(agent["thinking"], 1):
                        f.write(f"  {j}. {think['content']}\n")

                if agent["output"]:
                    f.write(f"\n输出:\n{agent['output'][:1000]}...\n")

                f.write(f"\n结束: {agent['end_time']}\n")
                f.write(f"\n{'-'*60}\n\n")


# 全局日志实例
_logger_instance = None

def get_logger() -> AgentLogger:
    """获取全局日志实例"""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = AgentLogger()
    return _logger_instance
