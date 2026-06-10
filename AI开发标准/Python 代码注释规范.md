# 代码注释规范提示词

# 给 AI 的「代码注释规范」提示词

请你在输出 Python 代码时，**所有函数 / 方法 / 类**都必须写出规范 Docstring，格式严格参考下面模板（与示例一致）。目标是：让任何人只看注释就能理解“这个函数/类干什么、怎么用、边界条件是什么”。

---

## 总要求

1. **使用 Google 风格 Docstring（如下模板），中文说明 + 关键字保持英文：** `Args / Returns / Raises / Examples / Attributes / TODO`
2. **类型注解必须完整**（函数参数、返回值；类属性可在 `Attributes` 写明）。
3. **异常要写清楚触发条件**（在 `Raises` 中逐条描述）。
4. **示例必须可运行**（放在 `Examples`，使用 `>>>` 形式）。
5. **TODO 用列表列出未来扩展点**（可选，没有则省略整个 TODO 段）。
6. **对输入进行校验**：类型不对抛 `TypeError`，取值范围/业务约束不满足抛 `ValueError`（按需）。

---

## 函数 Docstring 模板

```python
def function_name(param1: type, param2: type = default) -> return_type:
    """一句话说明函数做什么（动词开头，描述清楚输入输出）。

    Args:
        param1: 参数1的含义、期望类型/范围、是否允许为空。
        param2: 参数2的含义、默认值代表什么。

    Returns:
        return_type: 返回值含义、单位/格式、特殊情况（如空时返回什么）。

    Raises:
        TypeError: 何时触发类型错误。
        ValueError: 何时触发取值/业务约束错误。
        KeyError: （如需要）何时触发键缺失。
        RuntimeError: （如需要）何时触发运行时错误。

    Examples:
        >>> function_name(...)
        expected_output

    TODO:
        - 未来要支持的能力1
        - 未来要支持的能力2
    """
```

---

## 类 Docstring 模板

```python
class ClassName:
    """一句话说明这个类的职责（它表示/管理什么）。

    Attributes:
        attr1: 属性1含义、类型、取值范围/单位。
        attr2: 属性2含义、类型、何时会为空/默认值。
    """

    def __init__(self, ...):
        """初始化对象，说明必填/可选参数以及初始化后的状态。

        Args:
            ...
        """
```

---

## 输出规范（给 AI 的硬性约束）

- 你输出的每一个 `def` 都必须带 Docstring（除非是非常短的内部闭包；一般也要写）。
- 你输出的每一个 `class` 都必须带类 Docstring，并为 `__init__` 写 Docstring。
- 当你做了输入过滤（例如忽略非数字/忽略 0），必须在 Docstring 中写清楚规则与边界条件。
- 如果函数行为存在“开关参数”（例如 `ignore_zero`），必须在 `Args` 中解释其行为差异，并在 `Examples` 中至少给出一个示例。

---

## 参考示例（风格对齐）

> 下面只是风格参考；你写新代码时请按同样结构与严谨度输出。
> 

```python
def calculate_average(numbers: list[float | int], ignore_zero: bool = False) -> float:
    """计算一组数字的算术平均值。

    Args:
        numbers: 包含数字的列表，元素可以是整数或浮点数。
        ignore_zero: 是否忽略列表中的 0 值，默认为 False。

    Returns:
        float: 计算得到的算术平均值。

    Raises:
        ValueError: 当输入列表为空，或 ignore_zero=True 时列表全为 0。
        TypeError: 当输入不是列表，或列表元素不是数字类型。

    Examples:
        >>> calculate_average([1, 2, 3, 4])
        2.5
        >>> calculate_average([0, 1, 2, 3], ignore_zero=True)
        2.0

    TODO:
        - 支持加权平均值计算
        - 添加对 numpy 数组的原生支持
    """
    ...
```