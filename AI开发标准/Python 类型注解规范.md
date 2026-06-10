# Python 类型注解规范

## 给 AI 的「Python 类型注解（Type Hints）规范」

请你在输出 Python 代码时，必须遵循下面类型注解规范。目标是：让代码在 **mypy / pyright** 等静态检查工具下可读、可检查、可维护，并且在团队协作中风格统一。

---

## 总原则（必须遵守）

1. **优先使用现代写法（Python 3.9+ / 3.10+）**：
    - 容器类型用内置泛型：`list[str]`、`dict[str, int]`、`set[int]`、`tuple[int, int]`。
    - 联合类型优先用：`X | Y`（Python 3.10+）。
    - 只有在需要兼容旧版本时，才用 `typing.List` / `typing.Dict` / `typing.Union`。
2. **每个函数必须标注：参数类型 + 返回值类型**。
    - 无返回值用 `-> None`。
3. **可选值必须显式写出 `None`**：
    - `str | None`（推荐）或 `Optional[str]`。
    - 默认值为 `None` 时，注解也必须包含 `None`。
4. **不要滥用 Any**：
    - 只有在确实无法确定类型、或与动态数据边界交互（例如外部 JSON）时才使用 `Any`。
    - 能用 `TypedDict` / `Protocol` / `Mapping[str, object]` 表达就不要用 `Any`。
5. **集合/序列参数优先用抽象类型**（更通用）：
    - 只读输入倾向：`Sequence[T]` / `Mapping[K, V]`。
    - 会修改的集合倾向：`list[T]` / `dict[K, V]`。
6. **返回值类型要准确**：
    - 返回多个值用 `tuple[...]`。
    - 返回可迭代用 `Iterable[T]`；返回生成器用 `Iterator[T]` 或 `Generator[Yield, Send, Return]`。

---

## 最基础标准写法（必学）

### 1) 普通参数 + 返回值

```python
def greet(name: str, age: int) -> str:
    return f"Hello {name}, you are {age}"
```

### 2) 无返回值

```python
def log(message: str) -> None:
    print(message)
```

### 3) 可选参数（可以为 None）

```python
def get_user(user_id: int, name: str | None = None) -> dict[str, object]:
    return {"id": user_id, "name": name}
```

---

## 容器类型（Python 3.9+ 推荐）

```python
def sum_list(numbers: list[int]) -> int:
    return sum(numbers)

def calculate_total(items: dict[str, float]) -> float:
    return sum(items.values())

def get_point() -> tuple[int, int]:
    return (10, 20)

def unique_numbers(nums: set[int]) -> set[int]:
    return nums
```

---

## 联合类型（多种类型都允许）

```python
def add(a: int | float, b: int | float) -> int | float:
    return a + b
```

---

## 不确定类型（谨慎使用 Any）

```python
from typing import Any

def print_anything(data: Any) -> None:
    print(data)
```

---

## 函数作为参数（回调 Callable）

```python
from collections.abc import Callable

def process_data(data: int, func: Callable[[int], str]) -> str:
    return func(data)
```

---

## 自定义类类型注解

```python
class User:
    def __init__(self, name: str) -> None:
        self.name = name

def get_username(user: User) -> str:
    return user.name
```

---

## 企业级常用示例（完整）

```python
from __future__ import annotations

from collections.abc import Callable

class Product:
    def __init__(self, name: str, price: float) -> None:
        self.name = name
        self.price = price

def calculate_cart(
    products: list[Product],
    discount: float | None = None,
) -> float:
    total = sum(p.price for p in products)

    if discount is not None:
        total *= (1 - discount)

    return total

def foreach_product(
    products: list[Product],
    callback: Callable[[Product], None],
) -> None:
    for p in products:
        callback(p)
```

---

## 团队约定（建议直接复制到规范里）

- 新代码默认按 **Python 3.10+** 风格：`X | None`、`X | Y`、`list[T]`。
- 如果项目需要兼容 Python 3.8 及以下：统一改用 `Optional[X]`、`Union[X, Y]`、`List[T]`。
- 所有 PR 必须通过类型检查（mypy/pyright 其一），否则不合并。