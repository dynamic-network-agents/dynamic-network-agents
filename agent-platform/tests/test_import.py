"""agent_platform 包可导入性冒烟测试。"""

import agent_platform


def test_package_imports() -> None:
    assert isinstance(agent_platform.__version__, str)
