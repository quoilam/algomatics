"""
测试前置评估 — Stage 4 轻量级代码预检。
"""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from agents.evaluation_agent import EvaluationAgent


@pytest.fixture(scope="module")
def evaluator():
    return EvaluationAgent()


# ── 合格代码 ──

GOOD_CODE = """import cv2
import numpy as np

img = cv2.imread(input_image_path)
if img is None:
    raise ValueError("Cannot read input image")

result = cv2.GaussianBlur(img, (5, 5), 0)
cv2.imwrite(output_path, result)
print("Processing completed")
"""


def test_pre_evaluate_good_code(evaluator):
    result = evaluator.pre_evaluate_code(GOOD_CODE, "高斯模糊")
    assert result["quick_score"] >= 8.0
    assert result["should_revise"] is False
    assert len(result["issues"]) == 0
    assert result["checks"]["syntax_ok"] is True
    assert result["checks"]["has_input_var"] is True
    assert result["checks"]["has_output_var"] is True
    assert result["checks"]["has_output_save"] is True
    assert result["checks"]["has_imports"] is True


# ── 问题代码 ──

MISSING_OUTPUT_CODE = """import cv2

img = cv2.imread(input_image_path)
result = cv2.GaussianBlur(img, (5, 5), 0)
# 忘记保存了
"""


def test_pre_evaluate_missing_output(evaluator):
    result = evaluator.pre_evaluate_code(MISSING_OUTPUT_CODE, "高斯模糊")
    assert result["quick_score"] < 7.0
    assert any("output_path" in issue.lower() or "保存" in issue
               for issue in result["issues"])


MISSING_IMPORT_CODE = """img = Image.open(input_image_path)
img = img.filter(ImageFilter.BLUR)
img.save(output_path)
"""


def test_pre_evaluate_missing_imports(evaluator):
    result = evaluator.pre_evaluate_code(MISSING_IMPORT_CODE, "模糊")
    assert result["checks"]["has_imports"] is False
    assert any("导入" in issue or "import" in issue.lower()
               for issue in result["issues"])


SYNTAX_ERROR_CODE = """import cv2

img = cv2.imread(input_image_path)
result = cv2.GaussianBlur(img, (5, 5, 0)  # 缺少括号
cv2.imwrite(output_path, result)
"""


def test_pre_evaluate_syntax_error(evaluator):
    result = evaluator.pre_evaluate_code(SYNTAX_ERROR_CODE, "高斯模糊")
    assert result["checks"]["syntax_ok"] is False
    assert result["quick_score"] <= 3.0
    assert result["should_revise"] is True
    assert any("语法" in issue for issue in result["issues"])


MISSING_INPUT_VAR_CODE = """import cv2
from PIL import Image

img = cv2.imread("hardcoded_path.jpg")
cv2.imwrite(output_path, img)
"""


def test_pre_evaluate_missing_input_var(evaluator):
    result = evaluator.pre_evaluate_code(MISSING_INPUT_VAR_CODE, "模糊")
    assert result["checks"]["has_input_var"] is False
    assert any("input_image_path" in issue
               for issue in result["issues"])


# ── PIL 代码 ──

PIL_CODE = """from PIL import Image, ImageFilter

img = Image.open(input_image_path).convert('RGB')
img = img.filter(ImageFilter.MedianFilter(size=3))
img.save(output_path)
"""


def test_pre_evaluate_pil_code(evaluator):
    result = evaluator.pre_evaluate_code(PIL_CODE, "中值滤波")
    assert result["quick_score"] >= 8.0
    assert result["checks"]["has_imports"] is True
    assert result["checks"]["has_output_save"] is True


# ── 多问题代码 ──

MULTIPLE_ISSUES_CODE = """result = some_undefined_func(input_image_path)
# 没有 import，没有 output_path，还有未定义函数
"""


def test_pre_evaluate_multiple_issues(evaluator):
    result = evaluator.pre_evaluate_code(MULTIPLE_ISSUES_CODE, "测试")
    assert len(result["issues"]) >= 2
    assert result["should_revise"] is True


# ── 空代码 ──

def test_pre_evaluate_empty_code(evaluator):
    result = evaluator.pre_evaluate_code("", "测试")
    assert result["quick_score"] < 5.0


# ── Suggestion 生成 ──

def test_pre_evaluate_generates_suggestion(evaluator):
    result = evaluator.pre_evaluate_code(MISSING_OUTPUT_CODE, "高斯模糊")
    assert len(result["suggestion"]) > 0
    # 建议应提到具体问题
    assert "保存" in result["suggestion"] or "output_path" in result["suggestion"]
