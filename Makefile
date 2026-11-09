.PHONY: help install fmt lint typecheck test check-contracts check

UV := uv

help:
	@echo "动态通信网络多智能体系统 —— Python 侧工程命令"
	@echo "  make install         安装工作区依赖（uv sync，首次生成 uv.lock）"
	@echo "  make fmt             格式化（ruff format）"
	@echo "  make lint            静态检查（ruff check）"
	@echo "  make typecheck       类型检查（mypy）"
	@echo "  make test            单元测试（pytest）"
	@echo "  make check-contracts 契约 Schema 校验"
	@echo "  make check           fmt + lint + typecheck + test + check-contracts"

install:
	$(UV) sync

fmt:
	$(UV) run ruff format

lint:
	$(UV) run ruff check

typecheck:
	$(UV) run mypy

test:
	$(UV) run pytest

check-contracts:
	$(UV) run python scripts/check_contracts.py

check: fmt lint typecheck test check-contracts
