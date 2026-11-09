"""algorithms 包可导入性冒烟测试。"""

import algorithms


def test_package_imports() -> None:
    assert isinstance(algorithms.__version__, str)
