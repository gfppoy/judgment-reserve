from pathlib import Path
import shutil
import pytest
from judgment_reserve.util import ROOT


@pytest.fixture
def repo(tmp_path):
    for name in ("cases", "reference"):
        shutil.copytree(ROOT / name, tmp_path / name)
    return tmp_path
