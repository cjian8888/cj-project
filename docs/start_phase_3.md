# Phase 3 启动文档 - HTML报告渲染

## 背景

我正在进行穿云审计系统的初查报告引擎开发工作。

## 已完成阶段

- ✅ Phase -1: 归集配置（G-01 ~ G-05）
- ✅ Phase 0: 样本报告与数据契约（R-01 ~ R-07）
- ✅ **Phase 2: 报告结构重构（S-01 ~ S-06）**

## Phase 2 完成成果

### 1. 核心功能
已在 `investigation_report_builder.py` 中实现:
- `build_report_v3()` - v3.0三段式报告生成主函数
- `_build_preface()` - 前言章节生成
- 8个 `_build_person_section_X()` - 个人核查Section生成
- `_build_inter_company_analysis()` - 公司间交叉分析
- `_build_comprehensive_conclusion_v3()` - 综合研判生成

### 2. 报告结构
生成的JSON报告包含:
```json
{
  "meta": {...},                    // 元信息
  "preface": {...},                 // 前言章节
  "analysis_units": [...],          // 分析单元(每个含8个Section)
  "inter_company_analysis": {...},  // 公司间交叉分析
  "conclusion": {...}               // 综合研判
}
```

### 3. 测试验证
```bash
# 测试脚本
python3 test_report_v3.py

# 生成的报告
output/report_v3.json
```

## 当前阶段

**Phase 3: HTML报告渲染**

## Phase 3 任务目标

将JSON格式的v3.0报告渲染为专业的HTML报告,完全对照样本报告的样式和结构。

### 任务清单（H-01 ~ H-06）

| 任务ID | 任务名称 | 状态 | 预估时间 |
|--------|---------|------|---------|
| H-01 | 创建Jinja2模板框架 | ⬜ 待开始 | 2h |
| H-02 | 实现前言章节渲染 | ⬜ 待开始 | 1h |
| H-03 | 实现个人核查8个Section渲染 | ⬜ 待开始 | 6h |
| H-04 | 实现公司间交叉分析渲染 | ⬜ 待开始 | 2h |
| H-05 | 实现综合研判章节渲染 | ⬜ 待开始 | 2h |
| H-06 | 样式优化与测试 | ⬜ 待开始 | 2h |

## 关键设计原则

1. **对照样本报告**: 严格按照 `/templates/sample_report_complete.html` 的样式和结构
2. **专业话术**: 使用样本报告中的专业表述
3. **表格优先**: 数据展示优先使用表格形式
4. **风险标注**: 使用颜色标注风险等级(高/中/低)
5. **可打印**: 确保打印输出效果良好

## 参考文档

### 必读文档
1. **样本报告**: `/templates/sample_report_complete.html` - HTML结构和样式参考
2. **数据契约**: `/docs/report_data_contract.md` - 数据字段说明
3. **使用指南**: `/docs/report_v3_usage.md` - v3.0报告结构说明
4. **Phase 2总结**: 查看 `task.md` 和 `walkthrough.md` 了解已完成的工作

### 测试数据
1. **测试报告**: `output/report_v3.json` - 已生成的JSON报告
2. **测试配置**: `output/primary_targets.json` - 归集配置

## 技术选型

### 推荐方案
- **模板引擎**: Jinja2 (Python标准)
- **样式**: 内联CSS (便于打印和分发)
- **字体**: SimSun(宋体) - 符合公文规范
- **布局**: 表格布局 + 分页控制

### 目录结构
```
templates/
├── report_v3/
│   ├── base.html              # 基础模板
│   ├── preface.html           # 前言章节
│   ├── person_section_1.html # Section I: 身份与履历
│   ├── person_section_2.html # Section II: 资产存量
│   ├── person_section_3.html # Section III: 收入来源
│   ├── person_section_4.html # Section IV: 支出结构
│   ├── person_section_5.html # Section V: 收支匹配
│   ├── person_section_6.html # Section VI: 异常交易
│   ├── person_section_7.html # Section VII: 关联方往来
│   ├── person_section_8.html # Section VIII: 时空碰撞
│   ├── company_analysis.html  # 公司间交叉分析
│   └── conclusion.html        # 综合研判
```

## 实现步骤

### Step 1: 创建模板框架 (H-01)
1. 创建 `templates/report_v3/` 目录
2. 从 `sample_report_complete.html` 提取CSS样式
3. 创建 `base.html` 基础模板
4. 创建各个章节的子模板

### Step 2: 实现渲染引擎
1. 在 `investigation_report_builder.py` 中添加 `render_html_report_v3()` 方法
2. 配置Jinja2环境
3. 实现模板加载和渲染逻辑

### Step 3: 逐个实现章节渲染 (H-02 ~ H-05)
1. 前言章节 - 核查依据、数据范围、核查对象表格
2. 个人核查Section - 8个Section的表格和文字渲染
3. 公司间交叉分析 - 流向矩阵、闭环检测、共同上下游
4. 综合研判 - 问题汇总表、风险评级、工作建议

### Step 4: 样式优化 (H-06)
1. 对照样本报告调整样式
2. 添加分页控制
3. 优化打印效果
4. 测试不同浏览器兼容性

## 开始工作

在新对话中,请按照以下步骤继续:

```
1. 阅读本文档了解Phase 3目标
2. 查看样本报告 /templates/sample_report_complete.html
3. 查看测试数据 output/report_v3.json
4. 开始实现H-01: 创建Jinja2模板框架
```

## 验收标准

- [ ] HTML报告结构与样本报告一致
- [ ] 所有数据字段正确渲染
- [ ] 表格格式规范,边框清晰
- [ ] 风险标注颜色正确(红色=高,橙色=中)
- [ ] 打印输出效果良好
- [ ] 生成速度 < 3秒

## 示例命令

```bash
# 生成HTML报告
python3 -c "
from investigation_report_builder import load_investigation_report_builder
from report_config.primary_targets_service import PrimaryTargetsService

builder = load_investigation_report_builder('./output')
service = PrimaryTargetsService('./output')
config, _ = service.load_config()

# 生成JSON报告
report = builder.build_report_v3(config)

# 渲染HTML报告
html = builder.render_html_report_v3(report)

# 保存HTML文件
with open('./output/report_v3.html', 'w', encoding='utf-8') as f:
    f.write(html)

print('✅ HTML报告已生成: output/report_v3.html')
"
```

---

**创建时间**: 2026-01-23 20:45  
**当前Token使用**: 85k/200k  
**建议**: 在新对话中继续,避免token溢出  
**下一步**: 实现H-01 - 创建Jinja2模板框架
