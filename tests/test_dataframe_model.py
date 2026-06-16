import pandas as pd

from hermes.ui.dataframe_model import DataFrameTableModel


def test_model_can_show_complete_processing_results() -> None:
    dataframe = pd.DataFrame({"value": range(150)})
    model = DataFrameTableModel(preview_limit=100)

    model.set_dataframe(dataframe, limit_rows=False)

    assert model.rowCount() == 150
    assert model.visible_rows == 150
    assert model.total_rows == 150
