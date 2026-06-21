// MIKKY Conditional Image Input JS
import { app } from "../../scripts/app.js";

app.registerExtension({
    name: "MIKKY.ConditionalImageInput",
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name === "MIKKYConditionalImageInput") {
            const onExecuted = nodeType.prototype.onExecuted;
            nodeType.prototype.onExecuted = function (message) {
                onExecuted?.apply(this, arguments);
                // 在这里可以更新预览图
            };
        }
    }
});



