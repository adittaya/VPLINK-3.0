"""Small human-like interaction helpers (generic, site-agnostic)."""
from __future__ import annotations

import random
import time


def sleep(a: float = 0.4, b: float = 1.4) -> None:
    time.sleep(random.uniform(a, b))


def scroll_script(steps: int = 4) -> str:
    """JS snippet that scrolls the page in *steps* increments."""
    return (
        "(async (steps) => {"
        " for (let i = 1; i <= steps; i++) {"
        " window.scrollTo(0, (document.body.scrollHeight * i) / steps);"
        " await new Promise(r => setTimeout(r, 250));"
        " }})(" + str(int(steps)) + ");"
    )


def human_scroll(driver, steps: int = 4) -> None:
    driver.execute_script(scroll_script(steps))
    sleep(0.3, 0.9)
