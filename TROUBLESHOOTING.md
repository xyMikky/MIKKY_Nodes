# MIKKY Nodes 故障排除指南

## MIKKY Mask Editor 节点无法使用

### 问题：JS与Python命名不一致

如果MIKKY Mask Editor节点无法正常显示UI，可能是以下原因：

### 检查步骤

1. **确认节点名称一致**
   - Python文件 (`10_mask_editor.py`) 中注册的节点名称：`"MIKKYMaskEditorNode"`
   - JS文件 (`js/01_mask_editor.js`) 中检查的节点名称：`"MIKKYMaskEditorNode"`
   - 两者必须完全一致（区分大小写）

2. **检查JS文件路径**
   - 确保 `__init__.py` 中设置了 `WEB_DIRECTORY = "./js"`
   - 确保JS文件位于 `MIKKY_Nodes/js/` 目录下
   - 如果您的ComfyUI版本要求JS文件在 `web/` 目录，请将 `js/` 重命名为 `web/`

3. **检查浏览器控制台**
   - 打开浏览器开发者工具（F12）
   - 查看Console标签页
   - 如果看到 `[MIKKY Mask Editor] Detected node: ...` 说明JS文件已加载
   - 如果没有看到任何相关日志，说明JS文件可能未正确加载

4. **手动测试节点名称**
   - 在ComfyUI中创建MIKKY Mask Editor节点
   - 在浏览器控制台运行：`app.graph._nodes.find(n => n.type === "MIKKYMaskEditorNode")`
   - 检查返回的节点对象的 `type` 属性值

### 解决方案

如果节点名称确实不一致，请：

1. **检查Python注册**
   ```python
   NODE_CLASS_MAPPINGS = {
       "MIKKYMaskEditorNode": MIKKYMaskEditorNode  # 确保键名正确
   }
   ```

2. **检查JS匹配**
   ```javascript
   if (nodeData.name === "MIKKYMaskEditorNode") {  // 确保名称完全一致
   ```

3. **如果使用自动加载（__init__.py）**
   - 确保所有节点文件都正确导入
   - 检查控制台是否有加载错误信息

4. **如果手动整合**
   - 确保所有 `NODE_CLASS_MAPPINGS` 都合并到一个字典中
   - 确保没有重复的键名

### 常见问题

**Q: JS文件已加载但UI不显示**
A: 检查节点是否正确执行，查看Python控制台是否有错误信息

**Q: 节点名称在ComfyUI中显示不同**
A: 检查 `NODE_DISPLAY_NAME_MAPPINGS`，这是显示名称，不影响JS匹配

**Q: 使用__init__.py自动加载时节点不工作**
A: 尝试手动整合所有节点到一个 `nodes.py` 文件中



