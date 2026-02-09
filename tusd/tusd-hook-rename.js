/**
 * tusd Hook 服务 - 文件重命名
 * 
 * 监听 tusd 的 post-finish 事件，将上传的文件从 UUID 重命名为 metadata 中的 filename
 * 
 * 启动方式：
 *   node scripts/tusd-hook-rename.js
 * 
 * 配置 tusd：
 *   tusd -dir /path/to/upload -hooks-http http://localhost:3001/hooks -hooks-enabled-events post-finish -port 9000
 */

const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = process.env.TUSD_HOOK_PORT || 3001;
// 从环境变量读取上传目录，或使用默认值
const UPLOAD_DIR = process.env.TUSD_UPLOAD_DIR || 'C:\\DeadlineRepository10\\upload';

console.log(`[TUSD Hook] 服务启动配置:`);
console.log(`  端口: ${PORT}`);
console.log(`  上传目录: ${UPLOAD_DIR}`);

const server = http.createServer((req, res) => {
  // 设置 CORS 头
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  
  if (req.method === 'OPTIONS') {
    res.writeHead(200);
    res.end();
    return;
  }
  
  // 支持 /hooks 和 /hooks/post-finish 两种路径
  if (req.method === 'POST' && (req.url === '/hooks' || req.url === '/hooks/post-finish')) {
    let body = '';
    
    req.on('data', chunk => {
      body += chunk.toString();
    });
    
    req.on('end', () => {
      try {
        const data = JSON.parse(body);
        
        // tusd 的数据结构：{ Type: 'post-finish', Event: { Upload: {...}, HTTPRequest: {...} } }
        const eventType = data.Type;
        const event = data.Event || {};
        const upload = event.Upload || {};
        
        console.log('[TUSD Hook] 收到事件:', {
          type: eventType,
          uploadId: upload.ID,
          size: upload.Size,
          metaData: upload.MetaData
        });
        
        // 检查事件类型
        if (eventType !== 'post-finish') {
          console.log(`[TUSD Hook] 跳过非 post-finish 事件: ${eventType}`);
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ ok: true, skipped: true }));
          return;
        }
        
        // 获取元数据（MetaData 可能是对象，需要正确访问）
        const metaData = upload.MetaData || {};
        
        // 调试：打印完整的 MetaData 结构
        console.log('[TUSD Hook] MetaData 结构:', JSON.stringify(metaData, null, 2));
        
        // 尝试多种方式获取 filename
        let filename = metaData.filename;
        if (!filename && typeof metaData === 'object') {
          // 如果 MetaData 是对象但没有 filename 属性，尝试其他可能的键名
          filename = metaData['filename'] || metaData['name'] || null;
        }
        
        if (!filename) {
          console.warn('[TUSD Hook] 缺少 filename 元数据，跳过重命名');
          console.log('[TUSD Hook] 可用的 MetaData 键:', Object.keys(metaData));
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ ok: true, warning: 'No filename in metadata' }));
          return;
        }
        
        const uploadId = upload.ID;
        const storage = upload.Storage || {};
        const storagePath = storage.Path || uploadId;
        
        // 构建文件路径
        const oldPath = path.join(storagePath);
        const newPath = path.join(UPLOAD_DIR, filename);
        
        console.log(`[TUSD Hook] 准备重命名文件:`);
        console.log(`  Upload ID: ${uploadId}`);
        console.log(`  文件名 (metadata): ${filename}`);
        console.log(`  旧路径: ${oldPath}`);
        console.log(`  新路径: ${newPath}`);
        
        // 检查旧文件是否存在
        if (!fs.existsSync(oldPath)) {
          console.warn(`[TUSD Hook] 文件不存在: ${oldPath}`);
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ ok: true, warning: 'File not found' }));
          return;
        }
        
        // 检查新文件是否已存在
        if (fs.existsSync(newPath)) {
          console.warn(`[TUSD Hook] 目标文件已存在: ${newPath}，跳过重命名`);
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ ok: true, warning: 'Target file exists' }));
          return;
        }
        
        // 重命名文件
        try {
          fs.renameSync(oldPath, newPath);
          console.log(`[TUSD Hook] ✓ 文件重命名成功: ${storagePath} -> ${filename}`);
          
          // 如果存在 .info 文件，也重命名它
          const oldInfoPath = `${oldPath}.info`;
          const newInfoPath = `${newPath}.info`;
          if (fs.existsSync(oldInfoPath)) {
            fs.renameSync(oldInfoPath, newInfoPath);
            console.log(`[TUSD Hook] ✓ Info 文件重命名成功`);
          }
          
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ 
            ok: true, 
            renamed: true,
            oldPath: storagePath,
            newPath: filename
          }));
        } catch (renameError) {
          console.error(`[TUSD Hook] ✗ 文件重命名失败:`, renameError);
          res.writeHead(500, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ 
            ok: false, 
            error: renameError.message 
          }));
        }
      } catch (error) {
        console.error('[TUSD Hook] ✗ 处理请求时出错:', error);
        console.error('[TUSD Hook] 请求体:', body);
        res.writeHead(500, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ 
          ok: false, 
          error: error.message 
        }));
      }
    });
  } else {
    res.writeHead(404, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ error: 'Not found' }));
  }
});

server.listen(PORT, () => {
  console.log(`[TUSD Hook] 服务运行在端口 ${PORT}`);
  console.log(`[TUSD Hook] Hook URL: http://localhost:${PORT}/hooks`);
  console.log(`[TUSD Hook] 等待 tusd post-finish 事件...`);
});

// 处理错误
server.on('error', (error) => {
  console.error('[TUSD Hook] 服务器错误:', error);
  if (error.code === 'EADDRINUSE') {
    console.error(`[TUSD Hook] 端口 ${PORT} 已被占用，请更改端口或停止占用该端口的服务`);
  }
});

