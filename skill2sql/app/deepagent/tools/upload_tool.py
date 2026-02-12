"""
通用报告上传工具
用于将HTML报告自动上传到MinIO并返回访问链接
"""

import io
import os
from typing import Optional

from langchain_core.tools import tool

from common.minio_util import MinioUtils


@tool
def upload_html_report_to_minio(
    html_content: str,
    file_name: Optional[str] = None,
    bucket_name: str = "filedata",
) -> str:
    """
    将HTML报告内容上传到MinIO并返回预签名URL

    Args:
        html_content: HTML报告内容（字符串）
        file_name: 文件名（可选），如果不提供会自动生成带时间戳的文件名
        bucket_name: MinIO存储桶名称，默认为 "filedata"

    Returns:
        预签名URL字符串，有效期7天。格式：完整的HTTP/HTTPS URL

    Example:
        >>> html = "<html>...</html>"
        >>> url = upload_html_report_to_minio(html, "user_analysis_report.html")
        >>> print(url)  # 返回可访问的URL
    """
    try:
        # 如果没有提供文件名，生成带时间戳的文件名
        if not file_name:
            from datetime import datetime

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = f"report_{timestamp}.html"

        # 确保文件名以.html结尾
        if not file_name.endswith(".html"):
            file_name = f"{file_name}.html"

        # 将HTML内容转换为BytesIO
        html_bytes = io.BytesIO(html_content.encode("utf-8"))

        # 创建MinIO工具实例
        minio_utils = MinioUtils()

        # 确保bucket存在
        minio_utils.ensure_bucket(bucket_name)

        # 上传文件
        file_key = minio_utils.upload_to_minio_form_stream(
            html_bytes, bucket_name=bucket_name, file_name=file_name
        )

        if not file_key:
            return f"❌ 上传失败：无法获取文件键"

        # 获取预签名URL（有效期7天）
        report_url = minio_utils.get_file_url_by_key(
            bucket_name=bucket_name, object_key=file_key
        )

        return report_url

    except Exception as e:
        return f"❌ 上传失败：{str(e)}"


@tool
def upload_html_file_to_minio(
    file_path: str,
    file_name: Optional[str] = None,
    bucket_name: str = "filedata",
) -> str:
    """
    将本地HTML文件上传到MinIO并返回预签名URL

    Args:
        file_path: 本地HTML文件的完整路径
        file_name: 上传后的文件名（可选），如果不提供会使用原文件名
        bucket_name: MinIO存储桶名称，默认为 "filedata"

    Returns:
        预签名URL字符串，有效期7天。格式：完整的HTTP/HTTPS URL

    Example:
        >>> url = upload_html_file_to_minio("/path/to/report.html")
        >>> print(url)  # 返回可访问的URL
    """
    try:
        # 检查文件是否存在
        if not os.path.exists(file_path):
            return f"❌ 文件不存在：{file_path}"

        # 读取HTML文件内容
        with open(file_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        # 如果没有提供文件名，使用原文件名
        if not file_name:
            file_name = os.path.basename(file_path)

        # 如果没有提供文件名，生成带时间戳的文件名
        if not file_name:
            from datetime import datetime

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = f"report_{timestamp}.html"

        # 确保文件名以.html结尾
        if not file_name.endswith(".html"):
            file_name = f"{file_name}.html"

        # 将HTML内容转换为BytesIO
        html_bytes = io.BytesIO(html_content.encode("utf-8"))

        # 创建MinIO工具实例
        minio_utils = MinioUtils()

        # 确保bucket存在
        minio_utils.ensure_bucket(bucket_name)

        # 上传文件
        file_key = minio_utils.upload_to_minio_form_stream(
            html_bytes, bucket_name=bucket_name, file_name=file_name
        )

        if not file_key:
            return f"❌ 上传失败：无法获取文件键"

        # 获取预签名URL（有效期7天）
        report_url = minio_utils.get_file_url_by_key(
            bucket_name=bucket_name, object_key=file_key
        )

        return report_url

    except Exception as e:
        return f"❌ 上传失败：{str(e)}"
