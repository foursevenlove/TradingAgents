import logging
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tradingagents.dataflows import interface
from web.backend import stream_adapter
from web.backend.logging_config import HumanReadableFormatter


class RouteToVendorLoggingTest(unittest.TestCase):
    def setUp(self):
        interface._circuit_breaker._failures.clear()
        interface._circuit_breaker._last_failure.clear()
        interface._circuit_breaker._tripped.clear()

    def test_route_to_vendor_logs_vendor_failures_and_final_failure(self):
        def failing_akshare(*args, **kwargs):
            raise TimeoutError("akshare timed out")

        def failing_tushare(*args, **kwargs):
            raise RuntimeError("tushare quota exhausted")

        config = {
            "data_vendors": {"core_stock_apis": "akshare,tushare"},
            "tool_vendors": {},
            "tool_timeout": 1,
            "llm_timeout": {"default": 1},
            "llm_provider": "default",
        }

        with mock.patch.object(interface, "get_config", return_value=config), mock.patch.dict(
            interface.VENDOR_METHODS,
            {
                "get_stock_data": {
                    "akshare": failing_akshare,
                    "tushare": failing_tushare,
                }
            },
        ), self.assertLogs("tradingagents.web.dataflows", level=logging.INFO) as captured:
            with self.assertRaisesRegex(RuntimeError, "No available vendor"):
                interface.route_to_vendor(
                    "get_stock_data",
                    "600000.SH",
                    "2026-05-01",
                    "2026-05-16",
                )

        messages = [record.getMessage() for record in captured.records]
        self.assertTrue(any("Data source call failed" in message for message in messages))
        self.assertTrue(any("Data source fallback exhausted" in message for message in messages))

        failure_records = [
            record
            for record in captured.records
            if record.getMessage() == "Data source call failed"
        ]
        self.assertEqual([record.extra_data["vendor"] for record in failure_records], ["akshare", "tushare"])
        self.assertEqual(failure_records[0].extra_data["method"], "get_stock_data")
        self.assertEqual(
            failure_records[0].extra_data["args"],
            ["600000.SH", "2026-05-01", "2026-05-16"],
        )


class HumanReadableFormatterTest(unittest.TestCase):
    def test_human_readable_formatter_includes_extra_data(self):
        record = logging.LogRecord(
            name="tradingagents.web.analysis",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="Analysis task submitted",
            args=(),
            exc_info=None,
        )
        record.extra_data = {"task_id": "task-1", "stage": "api_start_analysis"}

        formatted = HumanReadableFormatter().format(record)

        self.assertIn("Analysis task submitted", formatted)
        self.assertIn('"task_id": "task-1"', formatted)
        self.assertIn('"stage": "api_start_analysis"', formatted)


class AgentLogNamingTest(unittest.TestCase):
    def test_agent_log_file_name_starts_with_creation_time(self):
        task_id = "12345678-1234-5678-1234-567812345678"

        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.dict(stream_adapter.WEB_CONFIG, {"log_dir": tmpdir}):
                logger = stream_adapter._get_agent_logger(task_id, "600000.SH", "2026-05-16")
                try:
                    handler = next(
                        handler
                        for handler in logger.handlers
                        if isinstance(handler, logging.handlers.RotatingFileHandler)
                    )
                    filename = Path(handler.baseFilename).name
                finally:
                    for handler in list(logger.handlers):
                        handler.close()
                        logger.removeHandler(handler)

        self.assertRegex(
            filename,
            r"^\d{8}_\d{6}_12345678_600000\.SH\.log$",
        )


if __name__ == "__main__":
    unittest.main()
