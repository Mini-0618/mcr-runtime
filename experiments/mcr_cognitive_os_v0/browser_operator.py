"""
browser_operator.py — MCR Cognitive OS v0.2 Mock Browser Operator

Defines the browser operator interface and a mock implementation.
Real browser control is deferred to MCR Operator (Stage 4).

NO real browser, NO network, NO Playwright.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class InteractiveElement:
    """A mock interactive element on a page."""
    index: int
    tag: str
    text: str
    element_type: str = "unknown"  # button, link, input, etc.


@dataclass
class PageState:
    """Mock browser page state."""
    url: str = "about:blank"
    title: str = "Mock Page"
    elements: List[InteractiveElement] = field(default_factory=list)
    has_screenshot: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "elements": [
                {"index": e.index, "tag": e.tag, "text": e.text, "type": e.element_type}
                for e in self.elements
            ],
            "has_screenshot": self.has_screenshot,
        }


@dataclass
class ActionResult:
    """Mock result of a browser action."""
    success: bool
    action: str
    details: str
    new_page_state: Optional[PageState] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "action": self.action,
            "details": self.details,
        }


class MockBrowserOperator:
    """Mock browser operator — returns fake data, never touches a real browser."""

    def __init__(self):
        self._current_page = PageState(
            url="https://example.com/mock",
            title="Mock Browser — MCR Cognitive OS v0.2",
            elements=[
                InteractiveElement(index=0, tag="button", text="Submit", element_type="button"),
                InteractiveElement(index=1, tag="a", text="Home", element_type="link"),
                InteractiveElement(index=2, tag="input", text="", element_type="input"),
                InteractiveElement(index=3, tag="button", text="Cancel", element_type="button"),
            ],
        )

    def observe(self) -> PageState:
        """Return current mock page state. Does NOT open a browser."""
        return self._current_page

    def propose_actions(self, task: str) -> List[Dict[str, Any]]:
        """Generate a mock action plan for a task. Does NOT execute anything."""
        task_lower = task.lower()
        actions = []

        if any(w in task_lower for w in ["click", "press", "button"]):
            actions.append({"action": "click", "target": 0, "reason": "Button interaction"})
        if any(w in task_lower for w in ["type", "input", "enter", "fill"]):
            actions.append({"action": "type", "target": 2, "text": "mock input", "reason": "Text input"})
        if any(w in task_lower for w in ["navigate", "go to", "open"]):
            actions.append({"action": "navigate", "url": "https://example.com/target", "reason": "Navigation"})
        if any(w in task_lower for w in ["read", "check", "observe", "see"]):
            actions.append({"action": "observe", "reason": "Page inspection"})

        # Default: just observe
        if not actions:
            actions.append({"action": "observe", "reason": "Default observation"})

        return actions

    def execute_mock(self, action: Dict[str, Any]) -> ActionResult:
        """Execute a mock action. Returns simulated result, no real browser."""
        action_type = action.get("action", "unknown")

        if action_type == "click":
            return ActionResult(
                success=True, action="click",
                details=f"Mock clicked element {action.get('target', 0)}",
            )
        elif action_type == "type":
            return ActionResult(
                success=True, action="type",
                details=f"Mock typed '{action.get('text', '')}' into element {action.get('target', 2)}",
            )
        elif action_type == "navigate":
            url = action.get("url", "https://example.com")
            self._current_page = PageState(
                url=url, title=f"Mock: {url}",
                elements=self._current_page.elements,
            )
            return ActionResult(
                success=True, action="navigate",
                details=f"Mock navigated to {url}",
            )
        elif action_type == "observe":
            return ActionResult(
                success=True, action="observe",
                details=f"Mock observed page: {self._current_page.title}, "
                        f"{len(self._current_page.elements)} elements",
            )
        else:
            return ActionResult(
                success=False, action=action_type,
                details=f"Unknown mock action: {action_type}",
            )
