import React, { useState, useEffect, useCallback } from 'react';
import { ShieldX, ShieldCheck, Upload, AlertTriangle, Loader, Copy, Check } from 'lucide-react';
import { THEME_COLOR } from '../constants';

const API_BASE = import.meta.env.VITE_API_URL || '';

async function fetchLicenseStatus() {
  const res = await fetch(`${API_BASE}/api/license/status`);
  return res.json();
}

async function uploadLicense(licenseObj) {
  const res = await fetch(`${API_BASE}/api/license/upload`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ license: licenseObj }),
  });
  return res.json();
}

const REASON_LABELS = {
  LICENSE_NOT_FOUND: '未找到许可证',
  LICENSE_PARSE_ERROR: '许可证格式错误',
  SIGNATURE_INVALID: '许可证签名无效',         
  MACHINE_ID_MISMATCH: '机器绑定不符',
  LICENSE_EXPIRED: '许可证已过期',
};

export default function LicenseGuard({ children }) {
  const [status, setStatus] = useState(null); // null = loading
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [copied, setCopied] = useState(false);

  const copyMachineId = () => {
    const text = status.current_machine_id;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }).catch(() => fallbackCopy(text));
    } else {
      fallbackCopy(text);
    }
  };

  const fallbackCopy = (text) => {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    try {
      document.execCommand('copy');
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (e) {
      console.error('复制失败', e);
    }
    document.body.removeChild(ta);
  };

  const checkLicense = useCallback(async () => {
    try {
      const data = await fetchLicenseStatus();
      setStatus(data);
    } catch {
      setStatus({ valid: false, reason: 'LICENSE_NOT_FOUND', message: '无法连接到服务器', current_machine_id: '' });
    }
  }, []);

  useEffect(() => {
    checkLicense();
  }, [checkLicense]);

  const handleFile = async (file) => {
    if (!file || !file.name.endsWith('.lic')) {
      setUploadResult({ success: false, message: '请选择 .lic 格式的许可证文件' });
      return;
    }

    setUploading(true);
    setUploadResult(null);

    try {
      const text = await file.text();
      const licenseObj = JSON.parse(text);
      const result = await uploadLicense(licenseObj);

      if (result.success) {
        setUploadResult({ success: true, message: `激活成功！客户: ${result.customer}，到期: ${result.expires_at}` });
        setTimeout(() => checkLicense(), 800);
      } else {
        setUploadResult({ success: false, message: result.message || '许可证验证失败' });
      }
    } catch (e) {
      setUploadResult({ success: false, message: e.message.includes('JSON') ? '文件不是合法的 JSON 格式' : e.message });
    } finally {
      setUploading(false);
    }
  };

  const onFileInput = (e) => handleFile(e.target.files[0]);

  const onDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    handleFile(e.dataTransfer.files[0]);
  };

  // Loading
  if (status === null) {
    return (
      <div className="fixed inset-0 bg-white flex items-center justify-center">
        <Loader size={32} className="animate-spin text-gray-400" />
      </div>
    );
  }

  // License valid
  if (status.valid) {
    return children;
  }

  // License invalid - show block screen with upload
  const reasonLabel = REASON_LABELS[status.reason] || '许可证无效';

  return (
    <div className="fixed inset-0 bg-gradient-to-br from-gray-50 to-gray-100 flex items-center justify-center p-4">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-2xl overflow-hidden border border-gray-100">
        <div className="h-1.5 w-full" style={{ backgroundColor: THEME_COLOR }} />

        <div className="p-8">
          {/* Header */}
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-xl bg-red-50 text-red-500 mb-4">
              <ShieldX size={32} strokeWidth={2} />
            </div>
            <h1 className="text-xl font-bold text-gray-800">
              WhatTech <span style={{ color: THEME_COLOR }}>MR</span> · 许可证未激活
            </h1>
            <div className="mt-3 inline-flex items-center gap-1.5 bg-red-50 text-red-600 text-sm px-3 py-1.5 rounded-lg">
              <AlertTriangle size={14} />
              {reasonLabel}：{status.message}
            </div>
          </div>

          {/* Upload Area */}
          <div
            className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors ${
              dragging ? 'border-[#39C5BB] bg-[#39C5BB]/5' : 'border-gray-200 hover:border-gray-300'
            }`}
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            onClick={() => document.getElementById('lic-file-input').click()}
          >
            <input
              id="lic-file-input"
              type="file"
              accept=".lic"
              className="hidden"
              onChange={onFileInput}
            />
            {uploading ? (
              <div className="flex flex-col items-center gap-2 text-gray-500">
                <Loader size={24} className="animate-spin" style={{ color: THEME_COLOR }} />
                <span className="text-sm">正在验证许可证…</span>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-2">
                <Upload size={24} className="text-gray-400" />
                <p className="text-sm font-medium text-gray-700">拖拽 <code className="bg-gray-100 px-1 rounded">.lic</code> 文件到此处</p>
                <p className="text-xs text-gray-400">或点击选择文件</p>
              </div>
            )}
          </div>

          {/* Upload Result */}
          {uploadResult && (
            <div className={`mt-3 flex items-start gap-2 text-sm px-4 py-3 rounded-xl ${
              uploadResult.success ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-600'
            }`}>
              {uploadResult.success
                ? <ShieldCheck size={16} className="mt-0.5 shrink-0" />
                : <AlertTriangle size={16} className="mt-0.5 shrink-0" />}
              <span>{uploadResult.message}</span>
            </div>
          )}

          {/* Machine ID */}
          {status.current_machine_id && (
            <div className="mt-6 bg-gray-50 rounded-xl p-4">
              <div className="flex items-center justify-between mb-1">
                <p className="text-xs text-gray-500">当前服务器机器 ID（发送给 WhatTech 申请许可证）</p>
                <button
                  onClick={copyMachineId}
                  className="flex items-center gap-1 text-xs px-2 py-1 rounded-lg transition-colors shrink-0 whitespace-nowrap"
                  style={copied ? { color: '#16a34a', backgroundColor: '#f0fdf4' } : { color: THEME_COLOR, backgroundColor: `${THEME_COLOR}15` }}
                >
                  {copied ? <Check size={12} /> : <Copy size={12} />}
                  {copied ? '已复制' : '复制'}
                </button>
              </div>
              <code className="text-xs text-gray-700 break-all leading-relaxed select-all">
                {status.current_machine_id}
              </code>
            </div>
          )}
        </div>

        <div className="bg-gray-50 px-8 py-3 text-center text-xs text-gray-400 border-t border-gray-100">
          © 2024 WhatTech Inc. · 联系邮箱: license@what-tech.cn
        </div>
      </div>
    </div>
  );
}
