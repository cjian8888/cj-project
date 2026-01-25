# 报告模板配置化改进方案

本文档提供了报告模板硬编码问题的改进方案。

## 当前问题分析

### 1. 样式硬编码
- CSS 样式直接写在模板中
- 字体、颜色、间距等样式值硬编码

### 2. 标题硬编码
- 报告标题格式固定
- 章节标题格式固定

### 3. 章节结构硬编码
- 章节顺序固定
- 章节内容固定

### 4. 缺少主题支持
- 无法切换不同的报告主题
- 无法自定义报告样式

## 改进方案

### 方案一：使用 Jinja2 模板继承

```python
# templates/base.html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}报告{% endblock %}</title>
    <style>
        /* 基础样式 - 可通过配置覆盖 */
        body {
            font-family: {{ config.font_family | default('"仿宋", "FangSong", serif') }};
            line-height: {{ config.line_height | default('1.8') }};
            margin: {{ config.margin_top | default('40px') }} {{ config.margin_bottom | default('60px') }};
            font-size: {{ config.font_size | default('16px') }};
            color: {{ config.text_color | default('#000') }};
        }
        
        /* 报告标题 */
        .report-title {
            text-align: center;
            font-size: {{ config.title_font_size | default('22px') }};
            font-weight: bold;
            font-family: {{ config.title_font_family | default('"方正小标宋", "黑体", sans-serif') }};
            margin: {{ config.title_margin | default('30px 0 20px 0') }};
        }
        
        /* 一级章节标题 */
        h1.section-title {
            font-size: {{ config.h1_font_size | default('18px') }};
            font-weight: bold;
            margin: {{ config.h1_margin | default('30px 0 15px 0') }};
            font-family: {{ config.h1_font_family | default('"黑体", "SimHei", sans-serif') }};
        }
        
        /* 二级章节标题 */
        h2.subsection-title {
            font-size: {{ config.h2_font_size | default('16px') }};
            font-weight: bold;
            margin: {{ config.h2_margin | default('20px 0 10px 0') }};
        }
        
        /* 三级标题 */
        h3.item-title {
            font-size: {{ config.h3_font_size | default('16px') }};
            font-weight: bold;
            margin: {{ config.h3_margin | default('15px 0 8px 0') }};
        }
        
        /* 表格样式 */
        table {
            width: 100%;
            border-collapse: collapse;
            margin: {{ config.table_margin | default('15px 0') }};
            font-size: {{ config.table_font_size | default('14px') }};
        }
        
        table, th, td {
            border: {{ config.table_border_width | default('1px') }} solid {{ config.table_border_color | default('#000') }};
        }
        
        th, td {
            padding: {{ config.cell_padding | default('8px 10px') }};
            text-align: center;
        }
        
        th {
            background-color: {{ config.th_background_color | default('#f0f0f0') }};
            font-weight: bold;
        }
        
        /* 风险提示 */
        .risk-high {
            color: {{ config.risk_high_color | default('#d9534f') }};
            font-weight: bold;
        }
        
        .risk-medium {
            color: {{ config.risk_medium_color | default('#f0ad4e') }};
        }
        
        /* 结论区块 */
        .conclusion-block {
            margin: {{ config.conclusion_margin | default('20px 0') }};
            padding: {{ config.conclusion_padding | default('15px') }};
            background-color: {{ config.conclusion_bg_color | default('#f9f9f9') }};
            border-left: {{ config.conclusion_border_width | default('4px') }} solid {{ config.conclusion_border_color | default('#5bc0de') }};
        }
        
        /* 危险提示区块 */
        .danger-block {
            margin: {{ config.danger_margin | default('15px 0') }};
            padding: {{ config.danger_padding | default('15px') }};
            background-color: {{ config.danger_bg_color | default('#f2dede') }};
            border-left: {{ config.danger_border_width | default('4px') }} solid {{ config.danger_border_color | default('#d9534f') }};
        }
    </style>
</head>
<body>
    {% block content %}{% endblock %}
</body>
</html>
```

### 方案二：创建报告配置模块

```python
# report_config.py
from typing import Dict, Any
from dataclasses import dataclass

@dataclass
class ReportTheme:
    """报告主题配置"""
    # 字体配置
    font_family: str = '"仿宋", "FangSong", serif'
    title_font_family: str = '"方正小标宋", "黑体", sans-serif'
    h1_font_family: str = '"黑体", "SimHei", sans-serif'
    
    # 字号配置
    font_size: str = '16px'
    title_font_size: str = '22px'
    h1_font_size: str = '18px'
    h2_font_size: str = '16px'
    h3_font_size: str = '16px'
    table_font_size: str = '14px'
    
    # 间距配置
    line_height: str = '1.8'
    margin_top: str = '40px'
    margin_bottom: str = '60px'
    title_margin: str = '30px 0 20px 0'
    h1_margin: str = '30px 0 15px 0'
    h2_margin: str = '20px 0 10px 0'
    h3_margin: str = '15px 0 8px 0'
    table_margin: str = '15px 0'
    
    # 颜色配置
    text_color: str = '#000'
    table_border_color: str = '#000'
    table_border_width: str = '1px'
    th_background_color: str = '#f0f0f0'
    cell_padding: str = '8px 10px'
    
    # 风险颜色
    risk_high_color: str = '#d9534f'
    risk_medium_color: str = '#f0ad4e'
    
    # 区块颜色
    conclusion_bg_color: str = '#f9f9f9'
    conclusion_border_color: str = '#5bc0de'
    conclusion_border_width: str = '4px'
    conclusion_margin: str = '20px 0'
    conclusion_padding: str = '15px'
    
    danger_bg_color: str = '#f2dede'
    danger_border_color: str = '#d9534f'
    danger_border_width: str = '4px'
    danger_margin: str = '15px 0'
    danger_padding: str = '15px'

@dataclass
class ReportConfig:
    """报告配置"""
    # 报告元信息
    title: str = '信息查询结果分析报告'
    subtitle: str = ''
    date_format: str = '%Y年%m月%d日'
    
    # 主题配置
    theme: ReportTheme = None
    
    # 章节配置
    sections: Dict[str, Any] = None
    
    # 自定义样式
    custom_css: str = ''
    
    # 打印配置
    print_margin_top: str = '20mm'
    print_margin_bottom: str = '25mm'
    print_font_size: str = '14px'

# 预定义主题
THEMES = {
    'default': ReportTheme(),
    'official': ReportTheme(
        font_family='"仿宋", "FangSong", serif',
        title_font_family='"方正小标宋", "黑体", sans-serif',
        h1_font_family='"黑体", "SimHei", sans-serif',
    ),
    'modern': ReportTheme(
        font_family='"微软雅黑", "Microsoft YaHei", sans-serif',
        title_font_family='"微软雅黑", "Microsoft YaHei", sans-serif',
        h1_font_family='"微软雅黑", "Microsoft YaHei", sans-serif',
        risk_high_color='#e74c3c',
        risk_medium_color='#f39c12',
    ),
    'minimal': ReportTheme(
        font_family='"Arial", sans-serif',
        title_font_family='"Arial", sans-serif',
        h1_font_family='"Arial", sans-serif',
        risk_high_color='#333333',
        risk_medium_color='#666666',
    ),
}

def get_report_config(theme_name: str = 'default') -> ReportConfig:
    """获取报告配置"""
    theme = THEMES.get(theme_name, THEMES['default'])
    return ReportConfig(theme=theme)
```

### 方案三：修改 report_generator.py 使用配置

```python
# report_generator.py
from report_config import get_report_config

def generate_html_report(profiles, suspicions, core_persons, involved_companies, 
                      output_path, family_summary, family_assets, cleaned_data,
                      theme_name: str = 'default'):
    """
    生成 HTML 报告
    
    Args:
        theme_name: 主题名称（default/official/modern/minimal）
    """
    # 获取报告配置
    config = get_report_config(theme_name)
    
    # 加载模板
    env = _get_jinja_env()
    template = env.get_template('report_v3/base.html')
    
    # 渲染模板
    html_content = template.render(
        config=config,
        profiles=profiles,
        suspicions=suspicions,
        core_persons=core_persons,
        involved_companies=involved_companies
    )
    
    # 保存文件
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
```

### 方案四：创建主题配置文件

```yaml
# config/report_themes.yaml
themes:
  default:
    font_family: '"仿宋", "FangSong", serif'
    title_font_family: '"方正小标宋", "黑体", sans-serif'
    font_size: '16px'
    title_font_size: '22px'
    text_color: '#000'
    risk_high_color: '#d9534f'
    risk_medium_color: '#f0ad4e'
  
  official:
    font_family: '"仿宋", "FangSong", serif'
    title_font_family: '"方正小标宋", "黑体", sans-serif'
    font_size: '16px'
    title_font_size: '22px'
    text_color: '#000'
    risk_high_color: '#d9534f'
    risk_medium_color: '#f0ad4e'
  
  modern:
    font_family: '"微软雅黑", "Microsoft YaHei", sans-serif'
    title_font_family: '"微软雅黑", "Microsoft YaHei", sans-serif'
    font_size: '16px'
    title_font_size: '22px'
    text_color: '#333'
    risk_high_color: '#e74c3c'
    risk_medium_color: '#f39c12'
  
  minimal:
    font_family: '"Arial", sans-serif'
    title_font_family: '"Arial", sans-serif'
    font_size: '16px'
    title_font_size: '22px'
    text_color: '#333'
    risk_high_color: '#333333'
    risk_medium_color: '#666666'
```

## 实施步骤

### 阶段一：创建配置模块
1. 创建 `report_config.py` 模块
2. 定义 `ReportTheme` 和 `ReportConfig` 类
3. 实现预定义主题
4. 实现配置加载函数

### 阶段二：重构模板
1. 创建 `templates/base.html` 基础模板
2. 使用 Jinja2 继承机制
3. 将硬编码样式替换为配置变量
4. 创建子模板（章节模板）

### 阶段三：修改生成器
1. 修改 `report_generator.py` 使用配置
2. 添加主题选择参数
3. 实现动态样式渲染

### 阶段四：创建主题配置文件
1. 创建 `config/report_themes.yaml`
2. 定义多个主题配置
3. 实现主题切换功能

## 最佳实践

1. **保持向后兼容**：默认主题应与现有样式一致
2. **提供主题选择**：允许用户选择不同的报告主题
3. **支持自定义**：允许用户自定义样式
4. **文档化配置**：提供详细的配置说明
5. **测试主题**：确保所有主题都能正确渲染

## 示例使用

```python
# 使用默认主题
generate_html_report(profiles, suspicions, core_persons, involved_companies, 
                      output_path, theme_name='default')

# 使用官方主题
generate_html_report(profiles, suspicions, core_persons, involved_companies, 
                      output_path, theme_name='official')

# 使用现代主题
generate_html_report(profiles, suspicions, core_persons, involved_companies, 
                      output_path, theme_name='modern')

# 使用极简主题
generate_html_report(profiles, suspicions, core_persons, involved_companies, 
                      output_path, theme_name='minimal')
```
