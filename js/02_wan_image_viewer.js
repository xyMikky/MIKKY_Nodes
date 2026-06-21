import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

app.registerExtension({
	name: "MIKKY.WanBatchImageViewer",
	async beforeRegisterNodeDef(nodeType, nodeData, app) {
		if (nodeData.name !== "MIKKYWanBatchImageViewer") {
			return;
		}

		const onNodeCreated = nodeType.prototype.onNodeCreated;
		nodeType.prototype.onNodeCreated = function() {
			if (onNodeCreated) onNodeCreated.apply(this, arguments);
			this.setSize([350, 450]); 
            this.resizable = true;
		};

		nodeType.prototype.onExecuted = function(message) {
			const r = message?.wan_thumbnails;
            const server_selected_index = message?.selected_index?.[0] || 0;

			if (!r || !this.widgets) return;
            
            const indexWidget = this.widgets.find(w => w.name === "index");
            
            if (this.galleryDomWidget) {
                this.galleryDomWidget.element.remove();
                this.widgets.splice(this.widgets.indexOf(this.galleryDomWidget), 1);
                this.galleryDomWidget = null;
            }

            // --- 创建容器 DOM ---
            const galleryContainer = document.createElement("div");
            this.galleryEl = galleryContainer;

            Object.assign(galleryContainer.style, {
                display: "grid",
                // 关键修改 1: 将 auto-fill 改为 auto-fit
                // 关键修改 2: minmax(100px, 1fr) 表示最小100px，最大无限(1fr)
                // 这样当节点变宽时，如果图片数量不足以换行，现有的图片就会自动变大填满整行
                gridTemplateColumns: "repeat(auto-fit, minmax(100px, 1fr))", 
                gridAutoRows: "max-content",
                gap: "5px",
                width: "100%",
                overflowY: "auto",
                padding: "4px",
                boxSizing: "border-box",
                backgroundColor: "#151515",
                borderRadius: "4px"
            });

            r.forEach((imgData, idx) => {
                const item = document.createElement("div");
                Object.assign(item.style, {
                    position: "relative",
                    aspectRatio: "1 / 1", // 保持正方形
                    width: "100%",        // 强制填满网格分配的空间
                    cursor: "pointer",
                    border: "2px solid #333",
                    borderRadius: "4px",
                    overflow: "hidden",
                    backgroundColor: "#000",
                    display: "flex",       // 居中图片
                    alignItems: "center",
                    justifyContent: "center"
                });

                if (idx === server_selected_index) {
                    item.style.borderColor = "#00FF00";
                    item.style.boxShadow = "inset 0 0 10px rgba(0,255,0,0.3)";
                }

                const img = document.createElement("img");
                img.src = api.apiURL(`/view?filename=${encodeURIComponent(imgData.filename)}&type=${imgData.type}&subfolder=${imgData.subfolder}`);
                Object.assign(img.style, {
                    maxWidth: "100%",     // 限制最大宽高，配合 object-contain
                    maxHeight: "100%",
                    width: "auto",
                    height: "auto",
                    objectFit: "contain", 
                    display: "block"
                });

                const tag = document.createElement("div");
                tag.textContent = `#${idx}`;
                Object.assign(tag.style, {
                    position: "absolute",
                    top: "0", left: "0",
                    background: "rgba(0,0,0,0.6)",
                    color: "white", fontSize: "12px",
                    padding: "2px 6px",
                    pointerEvents: "none"
                });

                item.onclick = () => {
                    if (indexWidget) {
                        indexWidget.value = idx;
                        Array.from(galleryContainer.children).forEach(c => c.style.borderColor = "#333");
                        item.style.borderColor = "#00FF00";
                    }
                };

                item.appendChild(img);
                item.appendChild(tag);
                galleryContainer.appendChild(item);
            });

            this.galleryDomWidget = this.addDOMWidget("wan_gallery", "div", galleryContainer, {
                serialize: false,
                hideOnZoom: false
            });

            this.updateGallerySize = () => {
                if (!this.galleryEl) return;
                // 计算高度逻辑保持不变，跟随节点高度
                const targetHeight = Math.max(50, this.size[1] - 70); 
                this.galleryEl.style.height = `${targetHeight}px`;
            };

            this.updateGallerySize();
		};

        const originalOnResize = nodeType.prototype.onResize;
        nodeType.prototype.onResize = function(size) {
            if (originalOnResize) originalOnResize.apply(this, arguments);
            if (this.updateGallerySize) {
                this.updateGallerySize();
            }
        };
	}
});



