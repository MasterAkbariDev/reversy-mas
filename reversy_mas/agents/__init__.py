from .adaptive import Adaptive
from .base import Agent
from .coordinator import Coordinator
from .strategies import Defensive, Greedy, Strategic

NAMES = (Strategic.name, Greedy.name, Defensive.name, Adaptive.name, Coordinator.name)


def create_agent(name: str, depth: int = 2) -> Agent:
    if name == Strategic.name:
        return Strategic(depth)
    if name == Greedy.name:
        return Greedy()
    if name == Defensive.name:
        return Defensive()
    if name == Adaptive.name:
        return Adaptive()
    if name == Coordinator.name:
        return Coordinator((Strategic(depth), Greedy(), Defensive(), Adaptive()))
    raise ValueError(f"Unknown agent: {name}")
