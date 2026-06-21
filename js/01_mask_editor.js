import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

app.registerExtension({
    name: "MIKKY.MaskEditor",
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        const nodeName = nodeData.name;
        
        // 精确匹配节点名称（必须与Python中NODE_CLASS_MAPPINGS的键名完全一致）
        if (nodeName === "MIKKYMaskEditorNode") {
            const onNodeCreated = nodeType.prototype.onNodeCreated;
            
            nodeType.prototype.onNodeCreated = function () {
                const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;
                
                // 防止重复创建：如果已经存在widget就不再创建
                if (!this.ae_widget) {
                    // 清理可能存在的旧DOM widget（防止序列化恢复时重复）
                    const oldWidgetIndex = this.widgets?.findIndex(w => w.name === "ae_editor_ui");
                    if (oldWidgetIndex !== undefined && oldWidgetIndex >= 0) {
                        this.widgets.splice(oldWidgetIndex, 1);
                    }
                    
                    this.ae_widget = new MIKKYAEMaskEditorWidget(this);
                    this.setSize([500, 650]);
                }
                
                return r;
            };

            const onResize = nodeType.prototype.onResize;
            nodeType.prototype.onResize = function (size) {
                if (onResize) onResize.apply(this, arguments);
                if (this.ae_widget) {
                    this.ae_widget.resize(size[0], size[1]);
                }
            };

            const onExecuted = nodeType.prototype.onExecuted;
            nodeType.prototype.onExecuted = function(message) {
                const r = onExecuted ? onExecuted.apply(this, arguments) : undefined;
                if (message && message.ae_images) {
                    this.ae_widget.updateData(message.ae_images, message.ae_masks || []);
                }
                return r;
            };
        }
    }
});

class MIKKYAEMaskEditorWidget {
    constructor(node) {
        this.node = node;
        this.images = []; 
        this.inputMasks = [];
        this.currentFrame = 0;
        this.brushSize = 25;
        this.maskStorage = {}; 

        // 状态追踪
        this.isDrawing = false;
        this.lastPos = { x: 0, y: 0 };
        this.currentCompositeOperation = "source-over"; 
        
        // 工具模式: 'add' (红色) 或 'sub' (蓝色)
        this.toolMode = 'add'; 
        this.currentStrokeStyle = "#ff0000";

        this.statusTimer = null; 
        this.cursorTimer = null; 
        this.isCursorVisible = false;

        this.element = this.createDOM();
        this.widget = node.addDOMWidget("ae_editor_ui", "Editor", this.element, {
            serialize: false,
            hideOnZoom: false
        });
        
        this.maskDataWidget = this.node.widgets.find(w => w.name === "mask_data");
        if (!this.maskDataWidget) {
            this.maskDataWidget = { name: "mask_data", value: "" };
            this.node.widgets.push(this.maskDataWidget);
        }
    }

    createDOM() {
        const container = document.createElement("div");
        container.style.cssText = `
            display: flex; flex-direction: column; background: #1a1a1a; border-radius: 8px;
            border: 2px solid #333; overflow: hidden; font-family: sans-serif;
            width: 100%; height: 100%; box-sizing: border-box; outline: none; transition: border-color 0.2s;
        `;
        container.tabIndex = 0;

        container.onfocus = () => { container.style.borderColor = "#2196F3"; };
        container.onblur = () => { container.style.borderColor = "#333"; };

        // Viewport
        this.viewport = document.createElement("div");
        this.viewport.style.cssText = "position: relative; width: 100%; background: #000; display: flex; justify-content: center; align-items: center; overflow: hidden; flex-grow: 1;";
        
        // Stack Container
        this.stackContainer = document.createElement("div");
        this.stackContainer.style.cssText = "position: relative; width: 0; height: 0; box-shadow: 0 0 10px rgba(0,0,0,0.5);";

        this.imgEl = new Image();
        this.imgEl.style.cssText = "display: block; width: 100%; height: 100%; pointer-events: none; user-select: none;";
        
        this.canvasInputMask = document.createElement("canvas");
        this.canvasInputMask.style.cssText = "position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; opacity: 0.6; mix-blend-mode: screen;";

        this.canvasDraw = document.createElement("canvas");
        this.canvasDraw.style.cssText = "position: absolute; top: 0; left: 0; width: 100%; height: 100%; cursor: crosshair; opacity: 0.7;";
        
        // 光标
        this.brushCursor = document.createElement("div");
        this.brushCursor.style.cssText = `
            position: absolute; 
            pointer-events: none; 
            border: 1px solid rgba(255, 255, 255, 0.9); 
            box-shadow: 0 0 2px rgba(0, 0, 0, 0.8);
            border-radius: 50%; 
            transform: translate(-50%, -50%);
            display: none; 
            z-index: 100;
        `;

        this.stackContainer.appendChild(this.imgEl);
        this.stackContainer.appendChild(this.canvasInputMask);
        this.stackContainer.appendChild(this.canvasDraw);
        this.stackContainer.appendChild(this.brushCursor); 
        this.viewport.appendChild(this.stackContainer);
        container.appendChild(this.viewport);

        // Controls
        this.controlsWrapper = document.createElement("div");
        this.controlsWrapper.style.cssText = "padding: 10px; background: #222; border-top: 1px solid #333; color: #ccc; flex-shrink: 0;";

        // Slider
        const row1 = document.createElement("div");
        row1.style.cssText = "display: flex; align-items: center; gap: 8px; margin-bottom: 8px;";
        
        this.slider = document.createElement("input");
        this.slider.type = "range";
        this.slider.min = 0; this.slider.max = 0; this.slider.value = 0;
        this.slider.style.cssText = "flex-grow: 1; height: 6px; accent-color: #e57373; cursor: pointer;";
        this.slider.disabled = true;

        this.frameInfo = document.createElement("span");
        this.frameInfo.innerText = "Empty";
        this.frameInfo.style.cssText = "font-size: 11px; font-variant-numeric: tabular-nums; width: 60px; text-align: right;";

        row1.appendChild(this.slider);
        row1.appendChild(this.frameInfo);
        this.controlsWrapper.appendChild(row1);

        // --- 工具切换按钮栏 ---
        const toolRow = document.createElement("div");
        toolRow.style.cssText = "display: flex; gap: 8px; justify-content: center; margin-bottom: 8px;";

        const createToolBtn = (text, mode, color) => {
            const btn = document.createElement("button");
            btn.innerText = text;
            btn.style.cssText = `
                flex: 1; padding: 6px; border-radius: 4px; cursor: pointer; font-size: 11px; font-weight: bold;
                background: #333; color: #aaa; border: 1px solid #444; transition: all 0.2s;
            `;
            btn.onclick = () => {
                this.toolMode = mode;
                this.updateToolButtons();
                // 暂时显示颜色提示
                this.statusDiv.innerText = mode === 'add' ? "Mode: Draw (Add Mask)" : "Mode: Erase Input (Subtract)";
                this.statusDiv.style.color = color;
                this.statusDiv.style.visibility = "visible";
            };
            return btn;
        };

        this.btnAdd = createToolBtn("🖌️ Draw (Add)", "add", "#e57373");
        this.btnSub = createToolBtn("🧼 Erase Input", "sub", "#64b5f6");

        toolRow.appendChild(this.btnAdd);
        toolRow.appendChild(this.btnSub);
        this.controlsWrapper.appendChild(toolRow);

        // Buttons (Clear)
        const row2 = document.createElement("div");
        row2.style.cssText = "display: flex; gap: 8px; align-items: center; flex-wrap: wrap;";
        
        this.btnClearFrame = document.createElement("button");
        this.btnClearFrame.innerText = "🗑 Current";
        this.btnClearFrame.style.cssText = "background: #333; color: #fff; border: 1px solid #444; padding: 4px 8px; border-radius: 4px; cursor: pointer; font-size: 11px;";

        this.btnClearAll = document.createElement("button");
        this.btnClearAll.innerText = "🗑 All Frames";
        this.btnClearAll.style.cssText = "background: #522; color: #fff; border: 1px solid #633; padding: 4px 8px; border-radius: 4px; cursor: pointer; font-size: 11px;";

        const legend = document.createElement("span");
        legend.innerText = "R-Click: Undo/Clear";
        legend.style.cssText = "font-size: 10px; color: #666; margin-left: auto;";

        row2.appendChild(this.btnClearFrame);
        row2.appendChild(this.btnClearAll);
        row2.appendChild(legend);
        this.controlsWrapper.appendChild(row2);

        // Status
        this.statusDiv = document.createElement("div");
        this.statusDiv.style.cssText = "font-size: 10px; color: #e57373; margin-top: 5px; height: 16px; line-height: 16px; text-align: center; font-weight: bold; overflow: hidden;";
        this.statusDiv.innerText = "";
        this.statusDiv.style.visibility = "hidden";
        this.controlsWrapper.appendChild(this.statusDiv);

        container.appendChild(this.controlsWrapper);

        this.ctxDraw = this.canvasDraw.getContext("2d");
        this.ctxInput = this.canvasInputMask.getContext("2d");

        this.updateToolButtons(); // 初始化按钮样式
        this.bindEvents(container);
        
        setTimeout(() => this.resize(this.node.size[0], this.node.size[1]), 100);

        return container;
    }

    updateToolButtons() {
        // 更新按钮激活状态样式
        const activeStyle = "background: #444; color: #fff; border-color: #666; box-shadow: inset 0 0 5px rgba(0,0,0,0.5);";
        const inactiveStyle = "background: #333; color: #aaa; border-color: #444; box-shadow: none;";

        if (this.toolMode === 'add') {
            this.btnAdd.style.cssText += activeStyle;
            this.btnAdd.style.borderLeft = "4px solid #e57373";
            this.btnSub.style.cssText += inactiveStyle;
            this.btnSub.style.borderLeft = "1px solid #444";
        } else {
            this.btnSub.style.cssText += activeStyle;
            this.btnSub.style.borderLeft = "4px solid #64b5f6";
            this.btnAdd.style.cssText += inactiveStyle;
            this.btnAdd.style.borderLeft = "1px solid #444";
        }
    }

    resize(nodeWidth, nodeHeight) {
        requestAnimationFrame(() => {
            this.fitCanvas();
        });
    }

    getCanvasPos(e) {
        const cssWidth = parseFloat(this.stackContainer.style.width) || this.stackContainer.clientWidth;
        const naturalWidth = this.canvasDraw.width;
        
        if (!cssWidth || !naturalWidth) return { x: 0, y: 0 };

        const scaleX = naturalWidth / cssWidth;
        const scaleY = this.canvasDraw.height / (parseFloat(this.stackContainer.style.height) || this.stackContainer.clientHeight);

        return { 
            x: e.offsetX * scaleX, 
            y: e.offsetY * scaleY 
        };
    }

    updateCursorVisual(e) {
        const naturalWidth = this.canvasDraw.width;
        const cssWidth = parseFloat(this.stackContainer.style.width);
        
        if (!naturalWidth || !cssWidth) return;

        const ratio = cssWidth / naturalWidth;
        const cursorSize = this.brushSize * ratio;
        
        this.brushCursor.style.width = `${cursorSize}px`;
        this.brushCursor.style.height = `${cursorSize}px`;
        this.brushCursor.style.left = `${e.offsetX}px`;
        this.brushCursor.style.top = `${e.offsetY}px`;
        
        // 根据工具模式改变光标颜色
        if (this.toolMode === 'add') {
            this.brushCursor.style.borderColor = "rgba(255, 100, 100, 0.9)";
        } else {
            this.brushCursor.style.borderColor = "rgba(100, 180, 255, 0.9)";
        }
        
        this.brushCursor.style.display = "block";
    }

    bindEvents(container) {
        this.resizeObserver = new ResizeObserver(() => {
            this.fitCanvas();
        });
        this.resizeObserver.observe(this.viewport);

        this.canvasDraw.addEventListener("wheel", (e) => {
            e.preventDefault(); 
            e.stopPropagation();

            const step = 2;
            if (e.deltaY < 0) {
                this.brushSize = Math.min(this.brushSize + step, 300);
            } else {
                this.brushSize = Math.max(this.brushSize - step, 1);
            }

            this.statusDiv.innerText = `Brush Size: ${this.brushSize}px`;
            this.statusDiv.style.color = "#ccc";
            this.statusDiv.style.visibility = "visible";
            if (this.statusTimer) clearTimeout(this.statusTimer);
            this.statusTimer = setTimeout(() => {
                this.updateStatus();
            }, 1000);

            this.isCursorVisible = true;
            this.updateCursorVisual(e);

            if (this.cursorTimer) clearTimeout(this.cursorTimer);
            this.cursorTimer = setTimeout(() => {
                this.brushCursor.style.display = "none";
                this.isCursorVisible = false;
            }, 800);

        }, { passive: false });

        this.canvasDraw.addEventListener("mousemove", (e) => {
            this.lastPos = this.getCanvasPos(e);

            if (this.isCursorVisible) {
                this.updateCursorVisual(e);
            }

            if (this.isDrawing) {
                this.ctxDraw.lineTo(this.lastPos.x, this.lastPos.y);
                this.ctxDraw.stroke();
            }
        });

        this.canvasDraw.addEventListener("mouseleave", () => {
            if (this.isDrawing) {
                const endDrawEvent = new Event('mouseup');
                this.canvasDraw.dispatchEvent(endDrawEvent);
            }
            this.brushCursor.style.display = "none";
            this.isCursorVisible = false;
        });

        container.addEventListener("keydown", (e) => {
            if (!this.images || this.images.length === 0) return;

            let delta = 0;
            if (e.key === "a" || e.key === "A" || e.key === "ArrowLeft") delta = -1;
            else if (e.key === "d" || e.key === "D" || e.key === "ArrowRight") delta = 1;

            // 快捷键切换工具：1=Add, 2=Sub
            if (e.key === "1") { this.toolMode = 'add'; this.updateToolButtons(); }
            if (e.key === "2") { this.toolMode = 'sub'; this.updateToolButtons(); }

            if (delta !== 0) {
                e.preventDefault(); 
                e.stopPropagation();

                const maxFrame = this.images.length - 1;
                const fromFrame = this.currentFrame;
                const newFrame = Math.max(0, Math.min(maxFrame, fromFrame + delta));
                
                if (newFrame !== this.currentFrame) {
                    if (this.isDrawing) {
                        this.maskStorage[this.currentFrame] = this.canvasDraw.toDataURL("image/png");
                        this.saveAllMasks();
                    }

                    // Shift + 切帧：复制当前帧遮罩到目标帧（用于快速连续标注）
                    if (e.shiftKey) {
                        const srcMask = this.maskStorage[fromFrame];
                        if (srcMask) {
                            this.maskStorage[newFrame] = srcMask;
                            this.saveAllMasks();
                        }
                    }

                    this.currentFrame = newFrame;
                    this.slider.value = this.currentFrame;
                    this.showFrame(this.currentFrame);
                }
            }
        });

        this.slider.addEventListener("mousedown", (e) => { e.stopPropagation(); container.focus(); });
        this.slider.oninput = (e) => {
            const newFrame = parseInt(e.target.value);
            if (newFrame !== this.currentFrame) {
                this.currentFrame = newFrame;
                this.showFrame(this.currentFrame);
            }
        };

        this.btnClearFrame.onclick = () => {
            this.ctxDraw.clearRect(0, 0, this.canvasDraw.width, this.canvasDraw.height);
            delete this.maskStorage[this.currentFrame];
            this.saveAllMasks();
            this.updateStatus();
            container.focus();
        };

        this.btnClearAll.onclick = () => {
            if(confirm("Clear masks for ALL frames?")) {
                this.ctxDraw.clearRect(0, 0, this.canvasDraw.width, this.canvasDraw.height);
                this.maskStorage = {};
                this.saveAllMasks();
                this.updateStatus();
            }
            container.focus();
        };

        this.canvasDraw.addEventListener("contextmenu", (e) => { 
            e.preventDefault(); 
            e.stopPropagation(); 
            return false; 
        });

        this.canvasDraw.addEventListener("mousedown", (e) => {
            e.stopPropagation(); 
            e.preventDefault();
            container.focus();
            
            this.brushCursor.style.display = "none";
            this.isCursorVisible = false;

            if (!this.images.length) return;
            
            this.isDrawing = true;
            this.ctxDraw.beginPath();
            this.ctxDraw.lineCap = "round";
            this.ctxDraw.lineJoin = "round";
            this.ctxDraw.lineWidth = this.brushSize;

            if (e.button === 0) {
                // 左键：根据工具模式决定颜色
                this.currentCompositeOperation = "source-over"; // 叠加模式
                if (this.toolMode === 'add') {
                    this.currentStrokeStyle = "#ff0000"; // 红色 = 添加
                } else {
                    this.currentStrokeStyle = "#0000ff"; // 蓝色 = 擦除输入
                }
            } else if (e.button === 2) {
                // 右键：真正的橡皮擦（擦除画板上的红或蓝）
                this.currentCompositeOperation = "destination-out";
                this.currentStrokeStyle = "rgba(0,0,0,1)";
            }

            this.ctxDraw.globalCompositeOperation = this.currentCompositeOperation;
            this.ctxDraw.strokeStyle = this.currentStrokeStyle;

            const pos = this.getCanvasPos(e);
            this.lastPos = pos;
            this.ctxDraw.moveTo(pos.x, pos.y);
            this.ctxDraw.lineTo(pos.x, pos.y);
            this.ctxDraw.stroke();
        });

        const endDraw = () => {
            if (this.isDrawing) {
                this.isDrawing = false;
                this.ctxDraw.closePath();
                this.ctxDraw.globalCompositeOperation = "source-over";
                this.maskStorage[this.currentFrame] = this.canvasDraw.toDataURL("image/png");
                this.saveAllMasks();
                this.updateStatus();
                container.focus();
            }
        };

        this.canvasDraw.addEventListener("mouseup", endDraw);
    }

    saveAllMasks() {
        if (this.maskDataWidget) {
            this.maskDataWidget.value = JSON.stringify(this.maskStorage);
        }
    }

    updateData(images, masks) {
        this.images = images || [];
        this.inputMasks = masks || [];
        
        if (!this.maskDataWidget.value) {
            this.maskStorage = {};
        } else {
            try {
                if (this.maskDataWidget.value.startsWith("{")) {
                    this.maskStorage = JSON.parse(this.maskDataWidget.value);
                }
            } catch(e) {}
        }

        if (this.images.length > 0) {
            this.slider.disabled = false;
            this.slider.max = this.images.length - 1;
            if (this.currentFrame >= this.images.length) this.currentFrame = 0;
            this.slider.value = this.currentFrame;
            this.showFrame(this.currentFrame);
        } else {
            this.frameInfo.innerText = "Empty";
        }
    }

    showFrame(index) {
        if (!this.images[index]) return;
        
        this.frameInfo.innerText = `${index + 1} / ${this.images.length}`;
        this.updateStatus();

        const imgInfo = this.images[index];
        const params = new URLSearchParams(imgInfo);
        params.append("format", "webp");
        this.imgEl.src = api.apiURL(`/view?${params.toString()}`);

        this.imgEl.onload = () => {
            this.fitCanvas();
            this.loadInputMask(index);
            
            this.ctxDraw.clearRect(0, 0, this.canvasDraw.width, this.canvasDraw.height);

            const resumeStroke = () => {
                // 如果正在画画过程中切换了帧（不太可能，但为了安全）恢复状态
                if (this.isDrawing) {
                    this.ctxDraw.globalCompositeOperation = this.currentCompositeOperation;
                    this.ctxDraw.strokeStyle = this.currentStrokeStyle;
                    this.ctxDraw.lineCap = "round";
                    this.ctxDraw.lineJoin = "round";
                    this.ctxDraw.lineWidth = this.brushSize;
                    this.ctxDraw.beginPath();
                    this.ctxDraw.moveTo(this.lastPos.x, this.lastPos.y);
                    this.ctxDraw.lineTo(this.lastPos.x, this.lastPos.y); 
                    this.ctxDraw.stroke();
                }
            };

            if (this.maskStorage[index]) {
                const storedMask = new Image();
                storedMask.onload = () => {
                    this.ctxDraw.globalCompositeOperation = "source-over";
                    this.ctxDraw.drawImage(storedMask, 0, 0);
                    resumeStroke();
                };
                storedMask.src = this.maskStorage[index];
            } else {
                resumeStroke();
            }
        };
    }

    fitCanvas() {
        if (!this.imgEl.naturalWidth) return;

        const vw = this.viewport.clientWidth;
        const vh = this.viewport.clientHeight;
        
        if (vw === 0 || vh === 0) return;

        const nw = this.imgEl.naturalWidth;
        const nh = this.imgEl.naturalHeight;

        const imgRatio = nw / nh;
        const viewportRatio = vw / vh;

        let finalW, finalH;

        if (imgRatio > viewportRatio) {
            finalW = vw;
            finalH = vw / imgRatio;
        } else {
            finalW = vh * imgRatio;
            finalH = vh;
        }

        this.stackContainer.style.width = `${finalW}px`;
        this.stackContainer.style.height = `${finalH}px`;

        if (this.canvasDraw.width !== nw || this.canvasDraw.height !== nh) {
            this.canvasDraw.width = nw;
            this.canvasDraw.height = nh;
            this.canvasInputMask.width = nw;
            this.canvasInputMask.height = nh;
        }
    }

    loadInputMask(index) {
        this.ctxInput.clearRect(0, 0, this.canvasInputMask.width, this.canvasInputMask.height);
        if (this.inputMasks.length > 0) {
            const maskIdx = Math.min(index, this.inputMasks.length - 1);
            const maskInfo = this.inputMasks[maskIdx];
            const mParams = new URLSearchParams(maskInfo);
            mParams.append("format", "webp");
            const maskImg = new Image();
            maskImg.src = api.apiURL(`/view?${mParams.toString()}`);
            maskImg.onload = () => {
                this.ctxInput.globalAlpha = 1.0;
                this.ctxInput.drawImage(maskImg, 0, 0, this.canvasInputMask.width, this.canvasInputMask.height);
            };
        }
    }

    updateStatus() {
        if (this.maskStorage[this.currentFrame]) {
             this.statusDiv.innerText = "● Mask Edited on this frame";
             this.statusDiv.style.color = "#e57373";
             this.statusDiv.style.visibility = "visible";
        } else {
            this.statusDiv.style.visibility = "hidden";
        }
    }
}

