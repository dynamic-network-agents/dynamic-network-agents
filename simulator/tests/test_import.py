"""simulator 包可导入性冒烟测试。"""

import simulator


def test_package_imports() -> None:
    assert isinstance(simulator.__version__, str)
