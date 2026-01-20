// 共享的清洗与最终稿提取工具

export const cleanRaw = (text?: string): string => {
  if (!text) return '';
  let t = String(text);
  // 统一换行符
  t = t.replace(/\r\n/g, '\n');

  // 移除 <think>...</think> 之类的内嵌思考标签
  t = t.replace(/<think>[\s\S]*?<\/think>/gi, '');

  // 如果后端使用 PROCEED[...] 包裹正文（并可能在结尾带有 TERMINATE_* 标记），
  // 则优先提取中间内容；否则再做一般性的移除处理。
  const proceedMatch = t.match(/PROCEED\[([\s\S]*?)\]/i);
  if (proceedMatch && proceedMatch[1]) {
    // 取出中间内容
    t = proceedMatch[1];
    // 如果内容被单/双引号包裹，去除外层引号
    t = t.replace(/^\s*['"]/, '').replace(/['"]\s*$/, '');
  } else {
    // 常规移除形式
    t = t.replace(/PROCEED\[[\s\S]*?\]/gi, '');
  }

  // 移除末尾可能的终止标记，例如 TERMINATE_HIGH / TERMINATE_LOW 等
  t = t.replace(/TERMINATE_[A-Z_]+\s*$/i, '');

  // 如果字符串里包含转义的换行（例如来自 JSON 的 "\\n"），把它们还原为真实换行
  // 这样页面显示时不会出现字面 "\n" 序列
  t = t.replace(/\\n/g, '\n').replace(/\\r/g, '\r').replace(/\\t/g, '\t');

  // 去掉可能的最外层 JSON 风格的引号包裹（如 '...'/"..."）后的残留转义
  t = t.replace(/^\s*['"]+/, '').replace(/['"]+\s*$/, '');

  // 移除可能以 PROCEED 开头的残留文字
  t = t.replace(/^\s*PROCEED[:\s-]*\n*/i, '');

  // 移除诸如 THINK:, THOUGHTS: 等行首标记及其后内容（若为纯思考流）—谨慎截断
  t = t.replace(/(^|\n)\s*(THINK|THOUGHTS|思考|推理)[:：]?[^\n]*\n?/gi, '\n');

  // 移除多余的连续空行
  t = t.replace(/\n{3,}/g, '\n\n');

  // 去除两端空白
  return t.trim();
};

export const extractFinal = (text?: string): string => {
  const cleaned = cleanRaw(text);
  if (!cleaned) return '';

  const startMarkers = ['【审查通过稿】', '【最终稿】', '审查通过稿：', '最终稿：'];
  const endMarkers = ['【主要修改说明】', '【修改意见】', '主要修改说明：', '修改意见：'];

  let startIdx = -1;
  for (const m of startMarkers) {
    const idx = cleaned.indexOf(m);
    if (idx !== -1) {
      startIdx = idx + m.length;
      break;
    }
  }

  let endIdx = -1;
  for (const em of endMarkers) {
    const idx = cleaned.indexOf(em);
    if (idx !== -1) {
      endIdx = idx;
      break;
    }
  }

  if (startIdx !== -1) {
    if (endIdx !== -1 && endIdx > startIdx) {
      return cleaned.substring(startIdx, endIdx).trim();
    }
    return cleaned.substring(startIdx).trim();
  }

  // 若未发现明确的起止标记，尝试按常见章节分隔符剔除“修改说明”之后的部分
  for (const em of endMarkers) {
    const idx = cleaned.indexOf(em);
    if (idx !== -1) return cleaned.substring(0, idx).trim();
  }

  return cleaned;
};
