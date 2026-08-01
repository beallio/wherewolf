from pathlib import Path

import polars as pl

from wherewolf.desktop.export_controller import ExportController
from wherewolf.services.export_destination import ExportFormat


def test_preview_export_controller_emits_one_terminal_result(qtbot, tmp_path: Path) -> None:
    controller = ExportController()
    with qtbot.waitSignal(controller.result_ready, timeout=3000) as blocker:
        assert controller.export(
            None, pl.DataFrame({"id": [1]}), tmp_path / "out.csv", ExportFormat.CSV, False
        )
    assert blocker.args[0].succeeded
    controller.shutdown()
