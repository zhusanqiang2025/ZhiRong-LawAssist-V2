/**
 * 合同审查插件 - 代码文件
 * 使用 OnlyOffice Builder API 实现高亮定位和修订功能
 */

(function(window, undefined){

    window.Asc.plugin.init = function(text) {
        // 隐藏默认按钮
        this.hideButton();

        // 初始化UI
        this.initUI();

        // 显示插件
        this.showButton();
    };

    window.Asc.plugin.initUI = function() {
        var plugin = this;

        // 搜索按钮
        document.getElementById('searchBtn').addEventListener('click', function() {
            var searchText = document.getElementById('searchInput').value;
            if (searchText && searchText.trim()) {
                plugin.highlightText(searchText.trim());
            } else {
                plugin.updateStatus('请输入要搜索的文本', 'warning');
            }
        });

        // 应用修订按钮
        document.getElementById('applyRevisionBtn').addEventListener('click', function() {
            var original = document.getElementById('originalText').value.trim();
            var newText = document.getElementById('newText').value.trim();

            if (!original || !newText) {
                plugin.updateStatus('请填写原文和建议文本', 'warning');
                return;
            }

            plugin.applyRevision(original, newText);
        });

        // 清空状态
        this.updateStatus('插件已就绪，等待操作...', '');
    };

    /**
     * 高亮定位文本
     */
    window.Asc.plugin.highlightText = function(searchText) {
        var plugin = this;

        this.updateStatus('正在搜索: ' + this.truncateText(searchText, 25), '');

        var oDocument = Api.GetDocument();
        var nCount = 0;

        // 使用 Builder API 搜索所有匹配
        var arrSearchResults = [];

        // 遍历所有段落
        var nParagraphsCount = oDocument.GetElementsCount();
        for (var nPara = 0; nPara < nParagraphsCount; nPara++) {
            var oParagraph = oDocument.GetElement(nPara);

            // 在段落中搜索
            var sParaText = oParagraph.GetText();
            if (sParaText && sParaText.indexOf(searchText) !== -1) {
                // 找到匹配，高亮显示
                var nStartPos = sParaText.indexOf(searchText);
                var nEndPos = nStartPos + searchText.length;

                // 高亮这段文本
                var oRange = oParagraph.GetRange(nStartPos, nEndPos);
                var oRun = oRange.GetBoundingContent()[0];
                if (oRun) {
                    oRun.SetHighlight(true);
                    oRun.SetHighlightColor(255, 255, 0); // 黄色
                    nCount++;
                }
            }
        }

        // 搜索表格
        var arrTables = oDocument.GetAllTables();
        for (var nTable = 0; nTable < arrTables.length; nTable++) {
            var oTable = arrTables[nTable];
            var nRowsCount = oTable.GetRowsCount();

            for (var nRow = 0; nRow < nRowsCount; nRow++) {
                var oRow = oTable.GetRow(nRow);
                var nCellsCount = oRow.GetCellsCount();

                for (var nCell = 0; nCell < nCellsCount; nCell++) {
                    var oCell = oRow.GetCell(nCell);
                    var oCellContent = oCell.GetContent();

                    // 在单元格内容中搜索
                    var nCellParaCount = oCellContent.GetElementsCount();
                    for (var nCellPara = 0; nCellPara < nCellParaCount; nCellPara++) {
                        var oCellPara = oCellContent.GetElement(nCellPara);
                        var sCellText = oCellPara.GetText();

                        if (sCellText && sCellText.indexOf(searchText) !== -1) {
                            var nStartPos = sCellText.indexOf(searchText);
                            var nEndPos = nStartPos + searchText.length;

                            var oRange = oCellPara.GetRange(nStartPos, nEndPos);
                            var arrRuns = oRange.GetBoundingContent();
                            for (var nRun = 0; nRun < arrRuns.length; nRun++) {
                                var oRun = arrRuns[nRun];
                                oRun.SetHighlight(true);
                                oRun.SetHighlightColor(255, 255, 0);
                                nCount++;
                            }
                        }
                    }
                }
            }
        }

        if (nCount > 0) {
            this.updateStatus('✓ 已找到并高亮 ' + nCount + ' 处匹配', 'success');
        } else {
            this.updateStatus('✗ 未找到匹配文本: ' + this.truncateText(searchText, 30), 'error');
        }
    };

    /**
     * 应用修订建议
     */
    window.Asc.plugin.applyRevision = function(originalText, newText) {
        this.updateStatus('正在应用修订...', '');

        var oDocument = Api.GetDocument();
        var bApplied = false;

        // 在段落中查找并替换
        var nParagraphsCount = oDocument.GetElementsCount();
        for (var nPara = 0; nPara < nParagraphsCount; nPara++) {
            var oParagraph = oDocument.GetElement(nPara);
            var sParaText = oParagraph.GetText();

            if (sParaText && sParaText.indexOf(originalText) !== -1) {
                // 找到了原文
                var nStartPos = sParaText.indexOf(originalText);
                var nEndPos = nStartPos + originalText.length;

                // 获取文本范围
                var oRange = oParagraph.GetRange(nStartPos, nEndPos);

                // 创建修订样式
                var arrRuns = oRange.GetBoundingContent();

                // 1. 设置原文为删除样式（红色删除线）
                for (var nRun = 0; nRun < arrRuns.length; nRun++) {
                    var oRun = arrRuns[nRun];
                    oRun.SetStrikeout(true);
                    oRun.SetColor(255, 0, 0);
                }

                // 2. 在原文后插入新文本（黄色高亮+下划线）
                var oNewRun = Api.CreateRun();
                oNewRun.AddText(" → "); // 分隔符
                oNewRun.SetColor(128, 128, 128);

                var oNewTextRun = Api.CreateRun();
                oNewTextRun.AddText(newText);
                oNewTextRun.SetHighlight(true);
                oNewTextRun.SetHighlightColor(255, 255, 0);
                oNewTextRun.SetUnderline(true);

                // 在段落末尾插入新内容
                oParagraph.AddDrawing(oNewRun);
                oParagraph.AddDrawing(oNewTextRun);

                bApplied = true;
                break; // 只替换第一个匹配
            }
        }

        // 如果在段落中没找到，尝试表格
        if (!bApplied) {
            var arrTables = oDocument.GetAllTables();
            for (var nTable = 0; nTable < arrTables.length; nTable++) {
                var oTable = arrTables[nTable];
                var nRowsCount = oTable.GetRowsCount();

                for (var nRow = 0; nRow < nRowsCount; nRow++) {
                    var oRow = oTable.GetRow(nRow);
                    var nCellsCount = oRow.GetCellsCount();

                    for (var nCell = 0; nCell < nCellsCount; nCell++) {
                        var oCell = oRow.GetCell(nCell);
                        var oCellContent = oCell.GetContent();

                        var nCellParaCount = oCellContent.GetElementsCount();
                        for (var nCellPara = 0; nCellPara < nCellParaCount; nCellPara++) {
                            var oCellPara = oCellContent.GetElement(nCellPara);
                            var sCellText = oCellPara.GetText();

                            if (sCellText && sCellText.indexOf(originalText) !== -1) {
                                var nStartPos = sCellText.indexOf(originalText);
                                var nEndPos = nStartPos + originalText.length;

                                var oRange = oCellPara.GetRange(nStartPos, nEndPos);
                                var arrRuns = oRange.GetBoundingContent();

                                for (var nRun = 0; nRun < arrRuns.length; nRun++) {
                                    var oRun = arrRuns[nRun];
                                    oRun.SetStrikeout(true);
                                    oRun.SetColor(255, 0, 0);
                                }

                                var oNewRun = Api.CreateRun();
                                oNewRun.AddText(" → ");
                                oNewRun.SetColor(128, 128, 128);

                                var oNewTextRun = Api.CreateRun();
                                oNewTextRun.AddText(newText);
                                oNewTextRun.SetHighlight(true);
                                oNewTextRun.SetHighlightColor(255, 255, 0);
                                oNewTextRun.SetUnderline(true);

                                oCellPara.AddElement(oNewRun, false);
                                oCellPara.AddElement(oNewTextRun, false);

                                bApplied = true;
                                break;
                            }
                        }

                        if (bApplied) break;
                    }

                    if (bApplied) break;
                }

                if (bApplied) break;
            }
        }

        if (bApplied) {
            this.updateStatus('✓ 修订已应用：' + this.truncateText(originalText, 20) + ' → ' + this.truncateText(newText, 20), 'success');

            // 清空输入框
            document.getElementById('originalText').value = '';
            document.getElementById('newText').value = '';
        } else {
            this.updateStatus('✗ 未找到原文，无法应用修订: ' + this.truncateText(originalText, 30), 'error');
        }
    };

    /**
     * 更新状态显示
     */
    window.Asc.plugin.updateStatus = function(message, type) {
        var statusEl = document.getElementById('status');
        if (statusEl) {
            statusEl.textContent = message;

            // 移除所有状态类
            statusEl.className = 'status';

            // 添加新状态类
            if (type) {
                statusEl.classList.add(type);
            }
        }
    };

    /**
     * 截断文本
     */
    window.Asc.plugin.truncateText = function(text, maxLength) {
        if (!text) return '';
        if (text.length <= maxLength) return text;
        return text.substring(0, maxLength) + '...';
    };

    /**
     * 按钮事件
     */
    window.Asc.plugin.button = function(id) {
        this.executeCommand("close", "");
    };

    window.Asc.plugin.executeCommand = function(command, data) {
        if (command === "close") {
            this.shutdown();
        }
    };

})(window, undefined);
