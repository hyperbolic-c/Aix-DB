"""
LLM服务模块
封装OpenAI SDK调用，支持多种模型
"""

import json
import logging
from typing import Optional, Dict, Any, List, AsyncGenerator
from openai import OpenAI

logger = logging.getLogger(__name__)


class LLMService:
    """
    LLM服务
    封装大语言模型调用
    """
    
    def __init__(
        self,
        base_url: str = 'https://api-inference.modelscope.cn/v1',
        api_key: str = 'ms-5f84f678-c565-4e9e-ab42-5244ce4ce74b',
        model: str = 'Qwen/Qwen3-235B-A22B-Instruct-2507',
    ):
        """
        初始化LLM服务
        
        Args:
            base_url: API基础URL
            api_key: API密钥
            model: 模型ID
        """
        self.client = OpenAI(
            base_url=base_url,
            api_key=api_key,
        )
        self.model = model
        logger.info(f"LLM服务初始化完成，模型: {model}")
    
    def generate_sql(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
    ) -> Dict[str, Any]:
        """
        生成SQL
        
        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            temperature: 温度参数
            
        Returns:
            包含success、sql、chart_type等的字典
        """
        try:
            logger.info("开始调用LLM生成SQL...")
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                stream=False,
            )
            
            content = response.choices[0].message.content
            logger.debug(f"LLM响应: {content}")
            
            # 解析JSON响应
            try:
                # 尝试直接解析
                result = json.loads(content)
            except json.JSONDecodeError:
                # 尝试从Markdown代码块中提取
                import re
                json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group(1))
                else:
                    # 尝试从文本中提取JSON
                    json_match = re.search(r'\{.*\}', content, re.DOTALL)
                    if json_match:
                        result = json.loads(json_match.group(0))
                    else:
                        raise ValueError(f"无法解析LLM响应: {content}")
            
            logger.info(f"SQL生成成功: {result.get('sql', 'N/A')}")
            return result
            
        except Exception as e:
            logger.error(f"LLM调用失败: {e}", exc_info=True)
            return {
                "success": False,
                "message": f"LLM调用失败: {str(e)}",
            }
    
    async def generate_sql_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
    ) -> AsyncGenerator[str, None]:
        """
        流式生成SQL
        
        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            temperature: 温度参数
            
        Yields:
            生成的文本片段
        """
        try:
            logger.info("开始流式调用LLM生成SQL...")
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                stream=True,
            )
            
            for chunk in response:
                if chunk.choices:
                    content = chunk.choices[0].delta.content
                    if content:
                        yield content
                        
        except Exception as e:
            logger.error(f"流式LLM调用失败: {e}", exc_info=True)
            yield f"错误: {str(e)}"
    
    def generate_summary(
        self,
        data_result: str,
        user_query: str,
        temperature: float = 0.3,
    ) -> str:
        """
        生成结果总结
        
        Args:
            data_result: 数据结果(JSON字符串)
            user_query: 用户问题
            temperature: 温度参数
            
        Returns:
            总结文本
        """
        try:
            system_prompt = """你是一个数据分析助手，根据查询结果生成简洁的自然语言总结。
请用中文回答，突出重点数据和关键指标。"""
            
            user_prompt = f"""用户问题: {user_query}

查询结果: {data_result}

请生成一段简洁的结果总结。"""
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                stream=False,
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"总结生成失败: {e}", exc_info=True)
            return f"查询执行成功，但总结生成失败: {str(e)}"
    
    def generate_recommendations(
        self,
        schema: str,
        current_question: str,
        num_recommendations: int = 3,
    ) -> List[str]:
        """
        生成推荐问题
        
        Args:
            schema: 数据库Schema
            current_question: 当前问题
            num_recommendations: 推荐问题数量
            
        Returns:
            推荐问题列表
        """
        try:
            system_prompt = f"""你是一个数据分析助手，根据数据库Schema和当前问题，生成{num_recommendations}个相关的推荐问题。
请用中文回答，返回JSON格式：{{"recommendations": ["问题1", "问题2", ...]}}"""
            
            user_prompt = f"""当前问题: {current_question}

数据库Schema:
{schema}

请生成{num_recommendations}个相关的推荐问题。"""
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                stream=False,
            )
            
            content = response.choices[0].message.content
            
            # 解析JSON
            try:
                result = json.loads(content)
                return result.get("recommendations", [])
            except json.JSONDecodeError:
                # 尝试从文本中提取
                import re
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group(0))
                    return result.get("recommendations", [])
                return []
            
        except Exception as e:
            logger.error(f"推荐问题生成失败: {e}", exc_info=True)
            return []


# 全局LLM服务实例
llm_service = LLMService()


def get_llm_service() -> LLMService:
    """获取LLM服务实例"""
    return llm_service
