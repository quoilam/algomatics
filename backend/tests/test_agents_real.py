"""
真实 API 测试模块 - 使用 .env 中的真实 API Key 进行测试

注意：这些测试会实际调用外部 API，请确保：
1. .env 文件中配置了正确的 API Key
2. 有足够的 API 配额
3. 网络连接正常

使用方法:
    python -m unittest backend.tests.test_agents_real -v
    
或者单独测试某个 Agent:
    python -m unittest backend.tests.test_agents_real.TestCodeGenerationAgentReal -v
    python -m unittest backend.tests.test_agents_real.TestEvaluationAgentReal -v
"""

import os
import sys
import unittest
import dotenv
from pathlib import Path

# 加载 .env 文件（从项目根目录）
env_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
dotenv.load_dotenv(env_path)

# 添加 backend 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestCodeGenerationAgentReal(unittest.TestCase):
    """真实 API 测试 - CodeGenerationAgent"""
    
    def setUp(self):
        """测试前准备"""
        self.api_key = os.getenv('OPENROUTER_API_KEY')
        if not self.api_key:
            self.skipTest('OPENROUTER_API_KEY not found in .env file')
        
        from backend.agents.code_generation_agent import CodeGenerationAgent
        self.agent = CodeGenerationAgent()
    
    def test_generate_simple_code(self):
        """测试生成简单代码"""
        code = self.agent.generate_code('Write a Python function that adds two numbers')
        
        # 验证返回的是字符串
        self.assertIsInstance(code, str)
        self.assertTrue(len(code) > 0)
        
        # 不应该包含错误信息
        self.assertNotIn('代码生成失败', code)
        print(f"\n生成的代码:\n{code}")
    
    def test_generate_image_processing_code(self):
        """测试生成图像处理代码"""
        code = self.agent.generate_code(
            '给图片添加复古滤镜，使用 OpenCV 或 PIL',
            search_results='Use cv2.cvtColor for color conversion'
        )
        
        self.assertIsInstance(code, str)
        self.assertTrue(len(code) > 0)
        self.assertNotIn('代码生成失败', code)
        print(f"\n生成的图像处理代码:\n{code}")
    
    def test_extract_code_block(self):
        """测试代码块提取（不需要 API）"""
        text_with_markdown = '''Here is the code:
```python
import cv2
def vintage_filter(img):
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
```
End of code.'''
        
        code = self.agent.extract_code_block(text_with_markdown)
        self.assertIn('import cv2', code)
        self.assertNotIn('```', code)
        print(f"\n提取的代码:\n{code}")


class TestEvaluationAgentReal(unittest.TestCase):
    """真实 API 测试 - EvaluationAgent"""
    
    def setUp(self):
        """测试前准备"""
        self.api_key = os.getenv('OPENROUTER_API_KEY')
        if not self.api_key:
            self.skipTest('OPENROUTER_API_KEY not found in .env file')
        
        from backend.agents.evaluation_agent import EvaluationAgent
        self.agent = EvaluationAgent()
        
        # 创建一个测试图片
        self.test_image_path = os.path.join(os.path.dirname(__file__), 'test_image.png')
        self._create_test_image()
    
    def _create_test_image(self):
        """创建一个简单的测试图片"""
        try:
            from PIL import Image
            img = Image.new('RGB', (100, 100), color='red')
            img.save(self.test_image_path)
        except ImportError:
            # 如果没有 PIL，创建一个假的 PNG 文件
            with open(self.test_image_path, 'wb') as f:
                f.write(b'\x89PNG\r\n\x1a\n' + b'\x00' * 100)
    
    def tearDown(self):
        """测试后清理"""
        if os.path.exists(self.test_image_path):
            os.remove(self.test_image_path)
    
    def test_evaluate_code(self):
        """测试代码评估"""
        code = '''
import cv2

def add_vintage_filter(image_path, output_path):
    img = cv2.imread(image_path)
    # Apply sepia tone
    sepia = cv2.transform(img, [[0.272, 0.534, 0.131],
                                 [0.349, 0.686, 0.168],
                                 [0.393, 0.769, 0.189]])
    cv2.imwrite(output_path, sepia)
'''
        result = self.agent.evaluate_code(code, '给图片添加复古滤镜')
        
        self.assertTrue(result['success'])
        self.assertIn('evaluation_text', result)
        print(f"\n代码评估结果:\n{result['evaluation_text']}")
    
    @unittest.skip('需要真实的图片文件，可能不稳定')
    def test_evaluate_image(self):
        """测试图片评估"""
        result = self.agent.evaluate_image(
            self.test_image_path,
            '创建一个红色测试图片'
        )
        
        self.assertTrue(result['success'])
        self.assertIn('evaluation_text', result)
        print(f"\n图片评估结果:\n{result['evaluation_text']}")


class TestExecutionAgentReal(unittest.TestCase):
    """真实 API 测试 - ExecutionAgent"""
    
    def setUp(self):
        """测试前准备"""
        from backend.agents.execution_agent import ExecutionAgent
        self.agent = ExecutionAgent()
        
        self.output_dir = os.path.join(os.path.dirname(__file__), 'output_test')
        os.makedirs(self.output_dir, exist_ok=True)
    
    def tearDown(self):
        """测试后清理"""
        import shutil
        if os.path.exists(self.output_dir):
            shutil.rmtree(self.output_dir)
    
    def test_execute_simple_code(self):
        """测试执行简单代码"""
        code = '''
import os
# 创建一个简单的输出文件
with open(output_path, 'w') as f:
    f.write('Execution successful')
'''
        result = self.agent.execute_code(code, output_filename='test_output.txt')
        
        self.assertTrue(result['success'])
        self.assertIn('成功', result['execution_log'])
        print(f"\n执行日志:\n{result['execution_log']}")
    
    def test_execute_code_with_error(self):
        """测试执行出错代码"""
        code = '''
raise ValueError('This is a test error')
'''
        result = self.agent.execute_code(code, output_filename='error_output.txt')
        
        self.assertFalse(result['success'])
        self.assertIn('ValueError', result['execution_log'])
        print(f"\n错误日志:\n{result['execution_log']}")


class TestRetrievalAgentReal(unittest.TestCase):
    """真实 API 测试 - RetrievalAgent"""
    
    def setUp(self):
        """测试前准备"""
        self.api_key = os.getenv('TAVILY_API_KEY')
        if not self.api_key:
            self.skipTest('TAVILY_API_KEY not found in .env file')
        
        from backend.agents.retrieval_agent import RetrievalAgent
        self.agent = RetrievalAgent()
    
    def test_search(self):
        """测试搜索功能"""
        query = 'image processing python opencv vintage filter'
        results = self.agent.search(query)
        
        self.assertIsInstance(results, str)
        self.assertTrue(len(results) > 0)
        print(f"\n搜索结果:\n{results[:500]}...")  # 只打印前 500 字符


class TestIntegrationReal(unittest.TestCase):
    """集成测试 - 真实 API"""
    
    def setUp(self):
        """测试前准备"""
        self.api_key = os.getenv('OPENROUTER_API_KEY')
        if not self.api_key:
            self.skipTest('OPENROUTER_API_KEY not found in .env file')
        
        from backend.agents.code_generation_agent import CodeGenerationAgent
        from backend.agents.evaluation_agent import EvaluationAgent
        
        self.code_agent = CodeGenerationAgent()
        self.eval_agent = EvaluationAgent()
    
    def test_generate_and_evaluate(self):
        """测试生成代码并评估"""
        # 生成代码
        code = self.code_agent.generate_code('Write a simple Python function to calculate factorial')
        
        self.assertIsInstance(code, str)
        self.assertNotIn('代码生成失败', code)
        
        # 评估代码
        result = self.eval_agent.evaluate_code(code, '计算阶乘的函数')
        
        self.assertTrue(result['success'])
        print(f"\n生成的代码:\n{code}")
        print(f"\n评估结果:\n{result['evaluation_text']}")


if __name__ == '__main__':
    # 运行测试
    unittest.main(verbosity=2)
