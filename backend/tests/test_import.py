"""backend 包可导入性冒烟测试。"""

import backend


def test_package_imports() -> None:
    assert isinstance(backend.__version__, str)
