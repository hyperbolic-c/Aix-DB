"""
模板加载器
从原实现 agent/text2sql/template/ 迁移
"""

import os
import yaml
from typing import Dict, Any, Optional


class TemplateLoader:
    """模板加载器"""
    
    def __init__(self, template_dir: Optional[str] = None):
        """
        Args:
            template_dir: 模板目录路径，默认为当前目录下的 yaml/
        """
        if template_dir is None:
            # 获取当前文件所在目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
            template_dir = os.path.join(current_dir, "yaml")
        
        self.template_dir = template_dir
        self._base_template: Optional[Dict] = None
        self._db_templates: Dict[str, Dict] = {}
    
    def load_base_template(self) -> Dict[str, Any]:
        """加载基础模板"""
        if self._base_template is None:
            template_path = os.path.join(self.template_dir, "template.yaml")
            with open(template_path, "r", encoding="utf-8") as f:
                self._base_template = yaml.safe_load(f)
        return self._base_template
    
    def load_sql_template(self, db_type: str) -> Dict[str, Any]:
        """加载数据库特定的 SQL 模板
        
        Args:
            db_type: 数据库类型，如 mysql, postgresql, oracle
        """
        if db_type not in self._db_templates:
            # 尝试加载数据库特定模板
            db_template_path = os.path.join(self.template_dir, f"{db_type}.yaml")
            
            if os.path.exists(db_template_path):
                with open(db_template_path, "r", encoding="utf-8") as f:
                    self._db_templates[db_type] = yaml.safe_load(f)
            else:
                # 如果没有特定模板，使用基础模板
                base = self.load_base_template()
                self._db_templates[db_type] = base.get("template", {})
        
        return self._db_templates[db_type]
    
    def get_process_check(self) -> str:
        """获取 SQL 生成检查步骤"""
        base = self.load_base_template()
        return base.get("template", {}).get("sql", {}).get("process_check", "")
    
    def get_query_limit_rule(self, enable_limit: bool = True) -> str:
        """获取数据量限制规则"""
        base = self.load_base_template()
        sql_template = base.get("template", {}).get("sql", {})
        
        if enable_limit:
            return sql_template.get("query_limit", "")
        else:
            return sql_template.get("no_query_limit", "")


# 全局模板加载器实例
_template_loader: Optional[TemplateLoader] = None


def get_template_loader() -> TemplateLoader:
    """获取全局模板加载器实例"""
    global _template_loader
    if _template_loader is None:
        _template_loader = TemplateLoader()
    return _template_loader
