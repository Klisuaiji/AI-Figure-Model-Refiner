"""Step state machine. Each step is independently a Task with
prepare / execute / validate / preview / commit / rollback.
"""


STEPS = [
    ("step_0", "Step 0 — 预处理与部件语义识别"),
    ("step_1", "Step 1 — 头发精修"),
    ("step_2", "Step 2 — 头/身/腿 比例校准"),
    ("step_3", "Step 3 — 衣体分离"),
    ("step_4", "Step 4 — 布料修复与加厚"),
    ("step_5", "Step 5 — 基座计算"),
    ("step_6", "Step 6 — 最终打印验证与 3MF 导出"),
]

STEP_COUNT = len(STEPS)


def step_name(i):
    if 0 <= i < STEP_COUNT:
        return STEPS[i][1]
    return "—"


class Pipeline:
    def __init__(self):
        self.current = 0

    def advance(self):
        self.current = min(self.current + 1, STEP_COUNT - 1)

    def back(self):
        self.current = max(self.current - 1, 0)

    def goto(self, i):
        self.current = max(0, min(i, STEP_COUNT - 1))