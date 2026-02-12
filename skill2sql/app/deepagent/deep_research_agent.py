"""
Deep Research Agent - 基于 DeepAgents 的 Report QA 智能体

重构说明：
1. 使用会话级工具调用管理器，解决死循环问题
2. 降低 recursion_limit，添加早期终止机制
3. 添加分步超时控制，解决任务超时问题
4. 增强进度追踪和状态监控
"""

import asyncio
import json
import logging
import os
import time
import traceback
from typing import Any, Dict, Optional

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver

from .tools.native_sql_tools import (
    set_native_datasource_info,
    sql_db_list_tables,
    sql_db_query,
    sql_db_query_checker,
    sql_db_schema,
    sql_db_table_relationship,
)
from .tools.tool_call_manager import get_tool_call_manager, set_current_session
from ..common.datasource_util import ConnectType, DatasourceInfo, get_connect_type
from ..common.llm_factory import create_llm
from ..schemas.responses import DataTypeEnum

logger = logging.getLogger(__name__)

current_dir = os.path.dirname(os.path.abspath(__file__))


class DeepAgent:
    """
    基于 DeepAgents 的 Report QA 智能体，支持多轮对话记忆

    优化特性：
    - 会话级工具调用管理，防止死循环
    - 分步超时控制，避免长时间阻塞
    - 智能循环检测和早期终止
    - 进度追踪和状态监控
    """

    DEFAULT_RECURSION_LIMIT = 400
    DEFAULT_LLM_TIMEOUT = 5 * 60
    STREAM_IDLE_TIMEOUT = 3 * 60
    TASK_TIMEOUT = 15 * 60
    MAX_MESSAGES = 100

    def __init__(self):
        self.checkpointer = InMemorySaver()
        self.ENABLE_TRACING = (
            os.getenv("LANGFUSE_TRACING_ENABLED", "false").lower() == "true"
        )

        self.running_tasks: Dict[str, Dict[str, Any]] = {}
        self._stream_end_sent: Dict[str, bool] = {}

        self.RECURSION_LIMIT = int(
            os.getenv("RECURSION_LIMIT", self.DEFAULT_RECURSION_LIMIT)
        )
        self.LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", self.DEFAULT_LLM_TIMEOUT))

        self.tool_manager = get_tool_call_manager()
        self.available_skills = self._load_available_skills()

    def _load_available_skills(self):
        """加载所有可用的技能"""
        skills_dir = os.path.join(current_dir, "skills")
        skills = []
        if os.path.exists(skills_dir):
            for skill_dir in os.listdir(skills_dir):
                skill_path = os.path.join(skills_dir, skill_dir)
                if os.path.isdir(skill_path):
                    skill_file = os.path.join(skill_path, "SKILL.md")
                    if os.path.exists(skill_file):
                        try:
                            with open(skill_file, "r", encoding="utf-8") as f:
                                content = f.read()
                                if content.startswith("---"):
                                    parts = content.split("---", 2)
                                    if len(parts) >= 3:
                                        frontmatter = parts[1]
                                        skill_info = {}
                                        for line in frontmatter.strip().split("\n"):
                                            if ":" in line:
                                                key, value = line.split(":", 1)
                                                skill_info[key.strip()] = (
                                                    value.strip().strip('"')
                                                )
                                        skill_info["name"] = skill_info.get(
                                            "name", skill_dir
                                        )
                                        skill_info["description"] = skill_info.get(
                                            "description", ""
                                        )
                                        skill_info["path"] = skill_path
                                        skill_info["dir"] = skill_dir
                                        skills.append(skill_info)
                        except Exception as exc:
                            logger.warning("加载技能 %s 失败: %s", skill_dir, exc)
        return skills

    def _resolve_skill_paths(self, requested):
        skills_dir = os.path.join(current_dir, "skills")
        if not requested:
            return [skills_dir]

        lookup = {}
        for skill in self.available_skills:
            name_key = str(skill.get("name", "")).lower()
            dir_key = str(skill.get("dir", "")).lower()
            if name_key:
                lookup[name_key] = skill.get("path")
            if dir_key:
                lookup[dir_key] = skill.get("path")

        selected = []
        for item in requested:
            key = str(item).lower().strip()
            if not key:
                continue
            path = lookup.get(key)
            if path and path not in selected:
                selected.append(path)

        if not selected:
            logger.warning("未匹配到请求的技能: %s，回退到全部技能", requested)
            return [skills_dir]
        return selected

    @staticmethod
    def _create_response(
        content: str,
        message_type: str = "continue",
        data_type: str = DataTypeEnum.ANSWER.value[0],
    ) -> str:
        res = {
            "data": {"messageType": message_type, "content": content},
            "dataType": data_type,
        }
        return "data:" + json.dumps(res, ensure_ascii=False) + "\n\n"

    def _wrap_tools_with_tracking(self, tools: list, session_id: str) -> list:
        from functools import wraps

        from langchain_core.tools import StructuredTool

        wrapped_tools = []

        for tool in tools:
            original_func = tool.func if hasattr(tool, "func") else tool._run
            tool_name = tool.name

            @wraps(original_func)
            def create_wrapper(orig_func, t_name):
                def wrapper(*args, **kwargs):
                    query = kwargs.get("query") or (args[0] if args else None)
                    allowed, reason = self.tool_manager.check_before_call(
                        session_id, t_name, query
                    )

                    if not allowed:
                        logger.warning("工具调用被阻止: %s, 原因: %s", t_name, reason)
                        return f"操作被阻止: {reason}"

                    try:
                        result = orig_func(*args, **kwargs)
                        self.tool_manager.record_call(session_id, t_name, True, query)
                        return result
                    except Exception:
                        self.tool_manager.record_call(session_id, t_name, False, query)
                        raise

                return wrapper

            wrapped_func = create_wrapper(original_func, tool_name)

            wrapped_tool = StructuredTool(
                name=tool.name,
                description=tool.description,
                func=wrapped_func,
                args_schema=tool.args_schema if hasattr(tool, "args_schema") else None,
            )
            wrapped_tools.append(wrapped_tool)

        logger.info("已包装 %d 个工具用于调用统计", len(wrapped_tools))
        return wrapped_tools

    def _create_sql_deep_agent(
        self,
        datasource: DatasourceInfo,
        llm_config: Dict[str, Any],
        session_id: str,
        skills: Optional[list] = None,
    ):
        if not datasource:
            raise ValueError("必须提供 datasource")

        logger.info("创建 Deep Agent - datasource: %s, session: %s", datasource.type, session_id)

        model = create_llm(llm_config, self.LLM_TIMEOUT)
        logger.info(
            "LLM 模型已创建，超时: %s秒，递归限制: %s",
            self.LLM_TIMEOUT,
            self.RECURSION_LIMIT,
        )

        connect_type = get_connect_type(datasource)

        if connect_type == ConnectType.sqlalchemy:
            logger.info("数据源 %s 使用 SQLAlchemy 连接", datasource.type)
            db = SQLDatabase.from_uri(
                datasource.uri,
                sample_rows_in_table_info=3,
                schema=datasource.db_schema,
            )
            toolkit = SQLDatabaseToolkit(db=db, llm=model)
            original_tools = toolkit.get_tools()
            sql_tools = self._wrap_tools_with_tracking(original_tools, session_id)
        else:
            logger.info("数据源 %s 使用原生工具连接", datasource.type)
            set_native_datasource_info(datasource, session_id)
            sql_tools = [
                sql_db_list_tables,
                sql_db_schema,
                sql_db_query,
                sql_db_query_checker,
                sql_db_table_relationship,
            ]

        try:
            from .tools.upload_tool import (
                upload_html_file_to_minio,
                upload_html_report_to_minio,
            )

            upload_tools = [upload_html_report_to_minio, upload_html_file_to_minio]
            all_tools = sql_tools + upload_tools
            logger.info("报告上传工具已加载")
        except ImportError as exc:
            logger.warning("报告上传工具导入失败: %s，仅使用SQL工具", exc)
            all_tools = sql_tools
        except Exception as exc:
            logger.warning("报告上传工具加载失败: %s，仅使用SQL工具", exc)
            all_tools = sql_tools

        skill_paths = self._resolve_skill_paths(skills)

        agent = create_deep_agent(
            model=model,
            memory=[os.path.join(current_dir, "AGENTS.md")],
            skills=skill_paths,
            tools=all_tools,
            backend=FilesystemBackend(root_dir=current_dir),
        )

        return agent

    async def run_agent(
        self,
        query: str,
        response,
        session_id: Optional[str] = None,
        task_id: Optional[str] = None,
        datasource: Optional[DatasourceInfo] = None,
        llm_config: Optional[Dict[str, Any]] = None,
        skills: Optional[list] = None,
        options: Optional[Dict[str, Any]] = None,
    ):
        if not datasource:
            error_msg = "❌ **错误**: 必须提供 datasource"
            await response.write(
                self._create_response(error_msg, "error", DataTypeEnum.ANSWER.value[0])
            )
            return

        if not llm_config:
            error_msg = "❌ **错误**: 必须提供 llm 配置"
            await response.write(
                self._create_response(error_msg, "error", DataTypeEnum.ANSWER.value[0])
            )
            return

        effective_task_id = task_id or session_id or "task"
        effective_session_id = session_id or effective_task_id

        set_current_session(effective_session_id)
        self.tool_manager.reset_session(effective_session_id)

        task_context = {
            "cancelled": False,
            "start_time": time.time(),
            "session_id": effective_session_id,
        }
        self.running_tasks[effective_task_id] = task_context
        self._stream_end_sent[effective_task_id] = False

        run_options = options or {}
        recursion_limit = int(run_options.get("recursion_limit", self.RECURSION_LIMIT))
        task_timeout = int(run_options.get("task_timeout", self.TASK_TIMEOUT))
        stream_idle_timeout = int(
            run_options.get("stream_idle_timeout", self.STREAM_IDLE_TIMEOUT)
        )
        max_messages = int(run_options.get("max_messages", self.MAX_MESSAGES))

        try:
            t02_answer_data = []

            config = {
                "configurable": {"thread_id": effective_session_id},
                "recursion_limit": recursion_limit,
            }

            if self.ENABLE_TRACING:
                from langfuse.langchain import CallbackHandler

                langfuse_handler = CallbackHandler()
                config["callbacks"] = [langfuse_handler]
                config["metadata"] = {"langfuse_session_id": effective_session_id}

            agent = self._create_sql_deep_agent(
                datasource, llm_config, effective_session_id, skills
            )

            stream_args = {
                "input": {"messages": [HumanMessage(content=query)]},
                "config": config,
                "stream_mode": "values",
            }

            try:
                await asyncio.wait_for(
                    self._execute_agent_stream(
                        agent,
                        stream_args,
                        response,
                        effective_task_id,
                        t02_answer_data,
                        effective_session_id,
                        query,
                        stream_idle_timeout,
                        max_messages,
                    ),
                    timeout=task_timeout,
                )
            except asyncio.TimeoutError:
                logger.error("任务 %s 总超时 (%s秒)", effective_task_id, task_timeout)
                await self._handle_timeout(response, "任务执行时间过长", effective_task_id)

        except asyncio.CancelledError:
            is_user_cancelled = self._is_task_cancelled(effective_task_id)
            logger.info(
                "任务 %s 被取消 - 原因: %s",
                effective_task_id,
                "用户主动取消" if is_user_cancelled else "连接断开",
            )
            try:
                await self._handle_task_cancellation(
                    response, effective_task_id, is_user_cancelled
                )
            except Exception as exc:
                if not self._is_connection_error(exc):
                    logger.error("处理取消异常时出错: %s", exc, exc_info=True)
        except Exception as exc:
            if self._is_connection_error(exc):
                logger.info("客户端连接已断开: %s", type(exc).__name__)
            else:
                logger.error("Agent运行异常: %s", exc)
                traceback.print_exception(exc)
                try:
                    error_msg = (
                        "❌ **错误**: 智能体运行异常\n\n```\n"
                        f"{str(exc)[:200]}\n```\n"
                    )
                    await self._safe_write(
                        response,
                        error_msg,
                        "error",
                        DataTypeEnum.ANSWER.value[0],
                        effective_task_id,
                    )
                except Exception:
                    pass
        finally:
            if effective_task_id in self.running_tasks:
                elapsed = time.time() - self.running_tasks[effective_task_id].get(
                    "start_time", 0
                )
                logger.info("任务 %s 结束，耗时: %.2f秒", effective_task_id, elapsed)
                del self.running_tasks[effective_task_id]

            if not self._stream_end_sent.get(effective_task_id):
                try:
                    await self._safe_write(
                        response,
                        "",
                        "end",
                        DataTypeEnum.STREAM_END.value[0],
                        effective_task_id,
                    )
                except Exception:
                    pass

            self._stream_end_sent.pop(effective_task_id, None)

            stats = self.tool_manager.get_stats(effective_session_id)
            logger.info("工具调用统计: %s", stats)

    async def _execute_agent_stream(
        self,
        agent,
        stream_args,
        response,
        task_id,
        t02_answer_data,
        session_id,
        query,
        stream_idle_timeout,
        max_messages,
    ):
        if self.ENABLE_TRACING:
            from langfuse import get_client

            langfuse = get_client()
            with langfuse.start_as_current_observation(
                input=query,
                as_type="agent",
                name="Report-QA",
            ) as rootspan:
                rootspan.update_trace(session_id=session_id)
                await self._stream_agent_response(
                    agent,
                    stream_args,
                    response,
                    task_id,
                    t02_answer_data,
                    session_id,
                    stream_idle_timeout,
                    max_messages,
                )
        else:
            await self._stream_agent_response(
                agent,
                stream_args,
                response,
                task_id,
                t02_answer_data,
                session_id,
                stream_idle_timeout,
                max_messages,
            )

    async def _stream_agent_response(
        self,
        agent,
        stream_args,
        response,
        task_id,
        t02_answer_data,
        session_id,
        stream_idle_timeout,
        max_messages,
    ):
        start_time = time.time()
        printed_count = 0
        connection_closed = False
        last_message_time = time.time()

        logger.info("开始流式响应处理 - 任务ID: %s", task_id)

        try:
            async for chunk in agent.astream(**stream_args):
                current_time = time.time()

                if self._is_task_cancelled(task_id):
                    await self._handle_task_cancellation(
                        response, task_id, is_user_cancelled=True
                    )
                    return

                ctx = self.tool_manager.get_session(session_id)
                if ctx.should_terminate:
                    logger.warning("工具调用管理器触发终止: %s", ctx.termination_reason)
                    await self._safe_write(
                        response,
                        f"\n> ⚠️ **执行中止**\n\n{ctx.termination_reason}",
                        "warning",
                        DataTypeEnum.ANSWER.value[0],
                        task_id,
                    )
                    break

                if current_time - last_message_time > stream_idle_timeout:
                    logger.warning("流式响应空闲超时 (%s秒)", stream_idle_timeout)
                    await self._handle_timeout(response, "长时间无响应", task_id)
                    break

                if "messages" in chunk:
                    messages = chunk["messages"]

                    if len(messages) > max_messages:
                        logger.warning("消息数量超过限制 (%s)", max_messages)
                        await self._safe_write(
                            response,
                            "\n> ⚠️ **对话过长**: 已达到消息数量上限，请开启新对话。",
                            "warning",
                            DataTypeEnum.ANSWER.value[0],
                            task_id,
                        )
                        break

                    if len(messages) > printed_count:
                        for msg in messages[printed_count:]:
                            if self._is_task_cancelled(task_id):
                                await self._handle_task_cancellation(
                                    response, task_id, is_user_cancelled=True
                                )
                                return

                            if not await self._print_message(
                                msg, response, t02_answer_data, task_id
                            ):
                                connection_closed = True
                                break

                            last_message_time = time.time()

                        printed_count = len(messages)

                        if connection_closed:
                            break

                        if hasattr(response, "flush"):
                            try:
                                await response.flush()
                            except Exception as exc:
                                if self._is_connection_error(exc):
                                    connection_closed = True
                                    break
                                raise
                        await asyncio.sleep(0)

        except asyncio.CancelledError:
            is_user_cancelled = self._is_task_cancelled(task_id)
            logger.info("任务 %s 流被取消", task_id)
            try:
                await self._handle_task_cancellation(response, task_id, is_user_cancelled)
            except Exception as exc:
                logger.error("处理取消异常时出错: %s", exc, exc_info=True)
            raise
        except Exception as exc:
            if self._is_connection_error(exc):
                logger.info("客户端连接已断开: %s", type(exc).__name__)
                connection_closed = True
            else:
                await self._handle_stream_error(response, exc, task_id)
        finally:
            elapsed_time = time.time() - start_time
            logger.info(
                "流式响应处理完成 - 任务ID: %s, 耗时: %.2f秒, 消息数: %s, 连接状态: %s",
                task_id,
                elapsed_time,
                printed_count,
                "已断开" if connection_closed else "正常",
            )

    async def _handle_timeout(self, response, reason: str, task_id: str):
        timeout_msg = (
            f"\n> ⚠️ **执行超时**: {reason}\n\n"
            "可能的原因：\n"
            "- 查询过于复杂\n"
            "- 数据量较大\n"
            "- 网络连接不稳定\n\n"
            "建议：\n"
            "- 简化查询条件\n"
            "- 分步骤执行\n"
            "- 稍后重试"
        )
        await self._safe_write(
            response, timeout_msg, "error", DataTypeEnum.ANSWER.value[0], task_id
        )
        await self._safe_write(
            response, "", "end", DataTypeEnum.STREAM_END.value[0], task_id
        )

    async def _handle_stream_error(self, response, exc: Exception, task_id: str):
        error_type = type(exc).__name__
        error_msg = str(exc).lower()

        is_timeout = (
            "timeout" in error_msg
            or "timed out" in error_msg
            or error_type in ["TimeoutError", "asyncio.TimeoutError"]
        )

        if is_timeout:
            logger.error("LLM 调用超时: %s: %s", error_type, exc, exc_info=True)
            await self._handle_timeout(response, "LLM 响应超时", task_id)
        else:
            logger.error("Agent 流式响应异常: %s: %s", error_type, exc, exc_info=True)
            try:
                err = (
                    "\n> ❌ **处理异常**\n\n"
                    f"错误类型: {error_type}\n"
                    f"错误信息: {str(exc)[:200]}\n\n"
                    "请稍后重试，如问题持续存在请联系管理员。"
                )
                await self._safe_write(
                    response, err, "error", DataTypeEnum.ANSWER.value[0], task_id
                )
                await self._safe_write(
                    response, "", "end", DataTypeEnum.STREAM_END.value[0], task_id
                )
            except Exception as write_error:
                logger.error("发送错误消息失败: %s", write_error, exc_info=True)

    def _is_task_cancelled(self, task_id: str) -> bool:
        return task_id in self.running_tasks and self.running_tasks[task_id].get(
            "cancelled", False
        )

    def _is_connection_error(self, exception: Exception) -> bool:
        error_type = type(exception).__name__
        error_msg = str(exception).lower()

        connection_error_types = [
            "ConnectionClosed",
            "ConnectionResetError",
            "BrokenPipeError",
            "ConnectionError",
            "OSError",
        ]

        connection_error_keywords = [
            "connection closed",
            "connection reset",
            "broken pipe",
            "client disconnected",
            "connection aborted",
            "transport closed",
        ]

        if error_type in connection_error_types:
            return True

        for keyword in connection_error_keywords:
            if keyword in error_msg:
                return True

        return False

    async def _safe_write(
        self,
        response,
        content: str,
        message_type: str = "continue",
        data_type: str = None,
        task_id: Optional[str] = None,
    ):
        try:
            if data_type is None:
                data_type = DataTypeEnum.ANSWER.value[0]
            await response.write(self._create_response(content, message_type, data_type))
            if data_type == DataTypeEnum.STREAM_END.value[0] and task_id:
                self._stream_end_sent[task_id] = True
            if hasattr(response, "flush"):
                await response.flush()
            return True
        except Exception as exc:
            if self._is_connection_error(exc):
                logger.info("客户端连接已断开: %s", type(exc).__name__)
                return False
            raise

    async def _handle_task_cancellation(
        self, response, task_id: str, is_user_cancelled: bool = True
    ):
        try:
            if is_user_cancelled:
                message = "\n> ⚠️ 任务已被用户取消"
            else:
                message = "\n> ⚠️ 连接已断开，任务已中断"

            await self._safe_write(
                response, message, "info", DataTypeEnum.ANSWER.value[0], task_id
            )
            await self._safe_write(
                response, "", "end", DataTypeEnum.STREAM_END.value[0], task_id
            )
        except Exception as exc:
            logger.error("发送取消消息失败: %s", exc, exc_info=True)

    async def _print_message(self, msg, response, t02_answer_data, task_id: str = None):
        if task_id and self._is_task_cancelled(task_id):
            return False

        try:
            if isinstance(msg, HumanMessage):
                content = msg.content if hasattr(msg, "content") else str(msg)
                if content and content.strip():
                    formatted_user_msg = self._format_user_message(content)
                    t02_answer_data.append(formatted_user_msg)
                    if not await self._safe_write(response, formatted_user_msg, task_id=task_id):
                        return False
            elif isinstance(msg, AIMessage):
                content = msg.content
                if isinstance(content, list):
                    text_parts = [
                        p.get("text", "")
                        for p in content
                        if isinstance(p, dict) and p.get("type") == "text"
                    ]
                    content = "\n".join(text_parts)

                if content and content.strip():
                    if task_id and self._is_task_cancelled(task_id):
                        return False

                    formatted_content = self._format_agent_content(content)
                    t02_answer_data.append(formatted_content)
                    if not await self._safe_write(response, formatted_content, task_id=task_id):
                        return False

                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        if task_id and self._is_task_cancelled(task_id):
                            return False

                        name = tc.get("name", "unknown")
                        args = tc.get("args", {})

                        tool_msg = self._format_tool_call(name, args)
                        if tool_msg:
                            if not await self._safe_write(response, tool_msg, "info", task_id=task_id):
                                return False
                            t02_answer_data.append(tool_msg)
            elif isinstance(msg, ToolMessage):
                if task_id and self._is_task_cancelled(task_id):
                    return False

                name = getattr(msg, "name", "")
                content_str = str(msg.content) if msg.content else ""
                tool_result_msg = self._format_tool_result(name, content_str)
                if tool_result_msg:
                    msg_type = "error" if "error" in content_str.lower() else "info"
                    if not await self._safe_write(response, tool_result_msg, msg_type, task_id=task_id):
                        return False
                    t02_answer_data.append(tool_result_msg)
            return True
        except Exception as exc:
            if self._is_connection_error(exc):
                logger.info("写入消息时连接断开: %s", type(exc).__name__)
                return False
            raise

    def _format_user_message(self, content: str) -> str:
        if not content or not content.strip():
            return content
        content = content.strip()
        return f"> 💬 **Question**\n> \n> {content}\n\n"

    def _format_agent_content(self, content: str) -> str:
        if not content or not content.strip():
            return content
        content = content.strip()
        return f"🤖 {content}\n\n"

    def _format_tool_call(self, name: str, args: dict) -> Optional[str]:
        if name == "sql_db_query":
            query = args.get("query", "")
            formatted_query = query.strip()
            return f"⚡ **Executing SQL**\n```sql\n{formatted_query}\n```\n\n"
        if name == "sql_db_schema":
            table_names = args.get("table_names", "")
            if isinstance(table_names, list):
                table_names = ", ".join(table_names)
            if table_names:
                return f"🔍 **Checking Schema:** `{table_names}`\n\n"
            return "🔍 **Checking Schema...**\n\n"
        if name == "sql_db_list_tables":
            return "📋 **Listing Tables...**\n\n"
        if name == "sql_db_query_checker":
            return "✅ **Validating Query...**\n\n"
        return None

    def _format_tool_result(self, name: str, content: str) -> Optional[str]:
        if "sql" in name.lower():
            if "error" not in content.lower():
                return "✓ Query executed successfully\n\n"
            error_content = content[:300].strip()
            return f"✗ **Query failed:** {error_content}\n\n"
        return None

    async def cancel_task(self, task_id: str) -> bool:
        if task_id in self.running_tasks:
            self.running_tasks[task_id]["cancelled"] = True
            session_id = self.running_tasks[task_id].get("session_id")
            if session_id:
                ctx = self.tool_manager.get_session(session_id)
                ctx.should_terminate = True
                ctx.termination_reason = "用户主动取消"
            return True
        return False

    def get_running_tasks(self):
        return list(self.running_tasks.keys())

    def get_available_skills(self):
        return self.available_skills
