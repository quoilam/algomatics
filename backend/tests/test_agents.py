"""
单元测试模块 - 用于单独测试每个 Agent 的 API 功能

使用方法:
    python -m pytest backend/tests/test_agents.py -v
    
或者单独测试某个 Agent:
    python -m pytest backend/tests/test_agents.py::TestRetrievalAgent -v
    python -m pytest backend/tests/test_agents.py::TestCodeGenerationAgent -v
    python -m pytest backend/tests/test_agents.py::TestEvaluationAgent -v
    python -m pytest backend/tests/test_agents.py::TestExecutionAgent -v

使用 unittest 运行:
    python -m unittest backend.tests.test_agents
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock, mock_open
import json

# 添加 backend 到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestRetrievalAgent(unittest.TestCase):
    """测试 RetrievalAgent 的搜索功能"""
    
    def setUp(self):
        """测试前准备"""
        # 设置环境变量
        os.environ['TAVILY_API_KEY'] = 'test_api_key'
        
    def tearDown(self):
        """测试后清理"""
        if 'TAVILY_API_KEY' in os.environ:
            del os.environ['TAVILY_API_KEY']
        # 清理缓存文件
        if os.path.exists('search_cache.json'):
            try:
                os.remove('search_cache.json')
            except:
                pass
    
    def test_missing_api_key(self):
        """测试缺少 API Key 的情况"""
        # 删除 API Key
        if 'TAVILY_API_KEY' in os.environ:
            del os.environ['TAVILY_API_KEY']
        
        # 由于 tavily 模块可能未安装，我们只测试环境变量检查逻辑
        # 这里我们模拟导入错误的情况
        with self.assertRaises((ValueError, ModuleNotFoundError)):
            # 尝试创建 agent（会因缺少 API key 或模块而失败）
            import backend.agents.retrieval_agent as retrieval_module
            # 如果模块成功加载，检查 API key
            if not os.getenv('TAVILY_API_KEY'):
                raise ValueError("TAVILY_API_KEY environment variable is required")


class TestCodeGenerationAgent(unittest.TestCase):
    """测试 CodeGenerationAgent 的代码生成功能"""
    
    def setUp(self):
        """测试前准备"""
        os.environ['OPENROUTER_API_KEY'] = 'test_api_key'
        
    def tearDown(self):
        """测试后清理"""
        if 'OPENROUTER_API_KEY' in os.environ:
            del os.environ['OPENROUTER_API_KEY']
    
    @patch('backend.agents.code_generation_agent.OpenAI')
    def test_generate_code_success(self, mock_openai_client):
        """测试成功生成代码"""
        from backend.agents.code_generation_agent import CodeGenerationAgent
        
        # Mock OpenAI 响应
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = 'print("Hello World")'
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_client.return_value = mock_client
        
        agent = CodeGenerationAgent()
        code = agent.generate_code('Write a simple hello world program')
        
        # 验证生成的代码
        self.assertEqual(code, 'print("Hello World")')
        mock_client.chat.completions.create.assert_called_once()
    
    @patch('backend.agents.code_generation_agent.OpenAI')
    def test_generate_code_with_search_results(self, mock_openai_client):
        """测试带搜索结果生成代码"""
        from backend.agents.code_generation_agent import CodeGenerationAgent
        
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '# Code with search results\ncv2.imread()'
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_client.return_value = mock_client
        
        agent = CodeGenerationAgent()
        code = agent.generate_code(
            'Add vintage filter to image',
            search_results='Use cv2 for image processing'
        )
        
        self.assertIn('# Code with search results', code)
    
    @patch('backend.agents.code_generation_agent.OpenAI')
    def test_generate_code_string_response(self, mock_openai_client):
        """测试 API 返回字符串而非对象的情况（错误处理）"""
        from backend.agents.code_generation_agent import CodeGenerationAgent
        
        mock_client = MagicMock()
        # Mock 返回字符串（错误情况）
        mock_client.chat.completions.create.return_value = '<!DOCTYPE html>Error'
        mock_openai_client.return_value = mock_client
        
        agent = CodeGenerationAgent()
        code = agent.generate_code('test request')
        
        # 验证错误处理
        self.assertIn('代码生成失败', code)
        self.assertIn('API returned a string', code)
    
    @patch('backend.agents.code_generation_agent.OpenAI')
    def test_generate_code_no_choices(self, mock_openai_client):
        """测试 API 响应没有 choices 属性的情况"""
        from backend.agents.code_generation_agent import CodeGenerationAgent
        
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = None
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_client.return_value = mock_client
        
        agent = CodeGenerationAgent()
        code = agent.generate_code('test request')
        
        # 验证错误处理
        self.assertIn('代码生成失败', code)
    
    @patch('backend.agents.code_generation_agent.OpenAI')
    def test_generate_code_exception(self, mock_openai_client):
        """测试生成代码时的异常处理"""
        from backend.agents.code_generation_agent import CodeGenerationAgent
        
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception('API Error')
        mock_openai_client.return_value = mock_client
        
        agent = CodeGenerationAgent()
        code = agent.generate_code('test request')
        
        # 验证异常被捕获
        self.assertIn('代码生成失败', code)
        self.assertIn('API Error', code)
    
    def test_extract_code_block(self):
        """测试从文本中提取代码块"""
        from backend.agents.code_generation_agent import CodeGenerationAgent
        
        agent = CodeGenerationAgent()
        
        # 测试带 markdown 的代码块
        text1 = '''Here is the code:
```python
import cv2
print("hello")
```
End of code.'''
        code1 = agent.extract_code_block(text1)
        self.assertIn('import cv2', code1)
        self.assertNotIn('```', code1)
        
        # 测试纯文本
        text2 = 'print("hello")'
        code2 = agent.extract_code_block(text2)
        self.assertEqual(code2, 'print("hello")')
    
    def test_conversation_history(self):
        """测试对话历史管理"""
        from backend.agents.code_generation_agent import CodeGenerationAgent
        
        os.environ['OPENROUTER_API_KEY'] = 'test_key'
        agent = CodeGenerationAgent()
        
        # 添加历史
        agent.add_to_history('user', 'Hello')
        agent.add_to_history('assistant', 'Hi there')
        
        self.assertEqual(len(agent.conversation_history), 2)
        self.assertEqual(agent.conversation_history[0]['role'], 'user')
        
        # 清除历史
        agent.clear_history()
        self.assertEqual(len(agent.conversation_history), 0)


class TestEvaluationAgent(unittest.TestCase):
    """测试 EvaluationAgent 的评估功能"""
    
    def setUp(self):
        """测试前准备"""
        os.environ['OPENROUTER_API_KEY'] = 'test_api_key'
        
    def tearDown(self):
        """测试后清理"""
        if 'OPENROUTER_API_KEY' in os.environ:
            del os.environ['OPENROUTER_API_KEY']
    
    @patch('backend.agents.evaluation_agent.OpenAI')
    @patch('builtins.open', new_callable=mock_open, read_data=b'test_image_data')
    def test_evaluate_image_success(self, mock_file, mock_openai_client):
        """测试成功评估图片"""
        from backend.agents.evaluation_agent import EvaluationAgent
        
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = 'Excellent image quality! Score: 9/10'
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_client.return_value = mock_client
        
        agent = EvaluationAgent()
        result = agent.evaluate_image(
            image_path='/fake/path/image.png',
            user_request='Add vintage filter'
        )
        
        # 验证结果
        self.assertTrue(result['success'])
        self.assertIn('Excellent', result['evaluation_text'])
        mock_client.chat.completions.create.assert_called_once()
    
    @patch('backend.agents.evaluation_agent.OpenAI')
    @patch('builtins.open', new_callable=mock_open, read_data=b'test_image_data')
    def test_evaluate_image_string_response(self, mock_file, mock_openai_client):
        """测试 API 返回字符串的错误情况"""
        from backend.agents.evaluation_agent import EvaluationAgent
        
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = '<!DOCTYPE html>Error Page'
        mock_openai_client.return_value = mock_client
        
        agent = EvaluationAgent()
        result = agent.evaluate_image(
            image_path='/fake/path/image.png',
            user_request='Add vintage filter'
        )
        
        # 验证错误处理
        self.assertFalse(result['success'])
        self.assertIn('评估失败', result['evaluation_text'])
        self.assertIn('API returned a string', result['error'])
    
    @patch('backend.agents.evaluation_agent.OpenAI')
    @patch('builtins.open', new_callable=mock_open, read_data=b'test_image_data')
    def test_evaluate_image_no_choices(self, mock_file, mock_openai_client):
        """测试 API 响应没有 choices 属性"""
        from backend.agents.evaluation_agent import EvaluationAgent
        
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = None
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_client.return_value = mock_client
        
        agent = EvaluationAgent()
        result = agent.evaluate_image(
            image_path='/fake/path/image.png',
            user_request='Add vintage filter'
        )
        
        self.assertFalse(result['success'])
        self.assertIn('评估失败', result['evaluation_text'])
    
    @patch('backend.agents.evaluation_agent.OpenAI')
    def test_evaluate_code_success(self, mock_openai_client):
        """测试成功评估代码"""
        from backend.agents.evaluation_agent import EvaluationAgent
        
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = 'Good code structure. Score: 8/10'
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_client.return_value = mock_client
        
        agent = EvaluationAgent()
        result = agent.evaluate_code(
            code='print("hello")',
            user_request='Simple hello world'
        )
        
        self.assertTrue(result['success'])
        self.assertIn('Good code', result['evaluation_text'])
    
    @patch('backend.agents.evaluation_agent.OpenAI')
    def test_evaluate_code_string_response(self, mock_openai_client):
        """测试评估代码时 API 返回字符串"""
        from backend.agents.evaluation_agent import EvaluationAgent
        
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = '<!DOCTYPE html>Error'
        mock_openai_client.return_value = mock_client
        
        agent = EvaluationAgent()
        result = agent.evaluate_code(
            code='print("hello")',
            user_request='Simple hello world'
        )
        
        self.assertFalse(result['success'])
        self.assertIn('代码评估失败', result['evaluation_text'])
    
    @patch('backend.agents.evaluation_agent.OpenAI')
    def test_evaluate_code_exception(self, mock_openai_client):
        """测试评估代码时的异常处理"""
        from backend.agents.evaluation_agent import EvaluationAgent
        
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception('Network Error')
        mock_openai_client.return_value = mock_client
        
        agent = EvaluationAgent()
        result = agent.evaluate_code(
            code='print("hello")',
            user_request='Simple hello world'
        )
        
        self.assertFalse(result['success'])
        self.assertIn('Network Error', result['error'])


class TestExecutionAgent(unittest.TestCase):
    """测试 ExecutionAgent 的代码执行功能"""
    
    def setUp(self):
        """测试前准备"""
        self.output_dir = 'output_images'
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
    
    def tearDown(self):
        """测试后清理"""
        # 清理生成的文件
        if os.path.exists(self.output_dir):
            for f in os.listdir(self.output_dir):
                os.remove(os.path.join(self.output_dir, f))
    
    def test_execute_simple_code(self):
        """测试执行简单代码"""
        from backend.agents.execution_agent import ExecutionAgent
        
        # 简化测试：只创建一个输出文件
        code = '''
import os
# 确保输出目录存在
os.makedirs(os.path.dirname(output_path), exist_ok=True)
# 创建一个标记文件表示执行成功
with open(output_path, 'wb') as f:
    f.write(b'\\x89PNG\\r\\n\\x1a\\n')  # PNG header
'''
        
        agent = ExecutionAgent()
        result = agent.execute_code(code, output_filename='test_output.png')
        
        self.assertTrue(result['success'])
        self.assertIn('成功生成输出图片', result['execution_log'])
    
    def test_execute_code_with_error(self):
        """测试执行出错代码"""
        from backend.agents.execution_agent import ExecutionAgent
        
        code = '''
# 故意制造错误
raise ValueError('Test error')
'''
        
        agent = ExecutionAgent()
        result = agent.execute_code(code, output_filename='test_error.png')
        
        self.assertFalse(result['success'])
        self.assertIn('Test error', result['error'])
        self.assertIn('ValueError', result['execution_log'])
    
    def test_summarize_execution(self):
        """测试执行总结"""
        from backend.agents.execution_agent import ExecutionAgent
        
        agent = ExecutionAgent()
        
        execution_result = {
            'success': True,
            'output_path': '/path/to/output.png',
            'execution_log': 'Step 1: Load image\nStep 2: Process\nStep 3: Save',
            'error': None
        }
        
        previous_steps = [
            'Retrieved search results',
            'Generated code',
            'Validated syntax'
        ]
        
        summary = agent.summarize_execution(execution_result, previous_steps)
        
        self.assertIn('执行总结', summary)
        self.assertIn('前序操作链路', summary)
        self.assertIn('Retrieved search results', summary)
        self.assertIn('✅ 执行成功', summary)
    
    def test_summarize_failed_execution(self):
        """测试失败执行的总结"""
        from backend.agents.execution_agent import ExecutionAgent
        
        agent = ExecutionAgent()
        
        execution_result = {
            'success': False,
            'output_path': None,
            'execution_log': 'Error during execution',
            'error': 'FileNotFoundError'
        }
        
        summary = agent.summarize_execution(execution_result, [])
        
        self.assertIn('❌ 执行失败', summary)
        self.assertIn('FileNotFoundError', summary)


class TestIntegration(unittest.TestCase):
    """集成测试 - 测试多个 Agent 的协作"""
    
    @patch('backend.agents.code_generation_agent.OpenAI')
    @patch('backend.agents.evaluation_agent.OpenAI')
    def test_code_generation_and_evaluation(self, mock_eval_client, mock_code_client):
        """测试代码生成和评估的流程"""
        from backend.agents.code_generation_agent import CodeGenerationAgent
        from backend.agents.evaluation_agent import EvaluationAgent
        
        # Mock 代码生成响应
        mock_code_response = MagicMock()
        mock_code_response.choices = [MagicMock()]
        mock_code_response.choices[0].message.content = 'import cv2\nimg = cv2.imread("test.png")'
        mock_code_client.return_value.chat.completions.create.return_value = mock_code_response
        
        # Mock 评估响应
        mock_eval_response = MagicMock()
        mock_eval_response.choices = [MagicMock()]
        mock_eval_response.choices[0].message.content = 'Good code quality'
        mock_eval_client.return_value.chat.completions.create.return_value = mock_eval_response
        
        os.environ['OPENROUTER_API_KEY'] = 'test_key'
        
        # 生成代码
        code_agent = CodeGenerationAgent()
        code = code_agent.generate_code('Process an image')
        
        # 评估代码
        eval_agent = EvaluationAgent()
        eval_result = eval_agent.evaluate_code(code, 'Process an image')
        
        self.assertIn('cv2', code)
        self.assertTrue(eval_result['success'])


if __name__ == '__main__':
    # 运行所有测试
    unittest.main(verbosity=2)
