## 文件组织
- 新业务代码放入 `src/`，按模块划分子目录
- 测试文件放入 `tests/`，目录结构与 `src/` 对应
- 不要将代码文件直接放在项目根目录

## API 响应格式
```json
{"success": true, "data": {...}, "error": null, "meta": {"page": 1, "total": 100}}
```

## 输出要求
- 完整的 API 端点实现代码与业务逻辑
- 输入验证和错误处理
- 对应的单元测试
- 运行 `python -m py_compile` 验证语法
- 写入实际文件
