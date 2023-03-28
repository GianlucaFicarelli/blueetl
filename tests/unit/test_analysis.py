from unittest.mock import patch

import pytest

from blueetl import analysis as test_module


@pytest.mark.parametrize("extract", [True, False])
@pytest.mark.parametrize("calculate", [True, False])
@pytest.mark.parametrize("show", [True, False])
@patch.object(test_module.MultiAnalyzer, "from_file")
def test_run_from_file(from_file, tmp_path, extract, calculate, show):
    analysis_config_file = tmp_path / "config.yaml"
    analysis_config_file.write_text("---")

    instance = test_module.run_from_file(
        analysis_config_file=analysis_config_file,
        extract=extract,
        calculate=calculate,
        show=show,
    )

    from_file.assert_called_once_with(analysis_config_file)
    assert instance.extract_repo.call_count == int(extract)
    assert instance.calculate_features.call_count == int(calculate)
    assert instance.show.call_count == int(show)
