"""Flow 模块 — 状态定义与流程编排"""

from src.flow.state import FilmProjectState

__all__ = ["FilmProductionFlow", "FilmProjectState"]


def __getattr__(name: str):
    """延迟导入 Flow 类（需要 crewai 依赖）"""
    if name == "FilmProductionFlow":
        from src.flow.film_production_flow import FilmProductionFlow
        return FilmProductionFlow
    raise AttributeError(f"module 'src.flow' has no attribute {name!r}")
