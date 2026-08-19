// Grok Imagine Dashboard - Client Application Logic

document.addEventListener('DOMContentLoaded', () => {
  initNavigation();
  initStudioForm();
  loadAllData();
  
  // Auto refresh stats every 15s
  setInterval(loadStats, 15000);
});

// ── Navigation & Tabs ──
function initNavigation() {
  const navButtons = document.querySelectorAll('.nav-item');
  navButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const tabId = btn.getAttribute('data-tab');
      switchTab(tabId);
    });
  });

  document.getElementById('btn-quick-draw')?.addEventListener('click', () => switchTab('studio'));
  document.getElementById('btn-quick-reg')?.addEventListener('click', () => triggerAutoReg());
}

function switchTab(tabId) {
  // Update sidebar active
  document.querySelectorAll('.nav-item').forEach(btn => {
    btn.classList.toggle('active', btn.getAttribute('data-tab') === tabId);
  });

  // Update tab panes
  document.querySelectorAll('.tab-pane').forEach(pane => {
    pane.classList.toggle('active', pane.id === `tab-${tabId}`);
  });

  // Update topbar header text
  const headings = {
    'dashboard': { title: 'Tổng Quan Hệ Thống', sub: 'Theo dõi Quota, sức khỏe kho tài khoản và lịch sử tạo ảnh thời gian thực' },
    'studio': { title: 'Imagine Studio', sub: 'Trực tiếp vẽ và sinh ảnh HD từ công nghệ FLUX của Grok AI' },
    'gallery': { title: 'Lịch Sử & Bộ Sưu Tập', sub: 'Thư viện toàn bộ các tác phẩm đã được tạo qua Web và API' },
    'accounts': { title: 'Kho Tài Khoản & Token', sub: 'Quản lý danh sách tài khoản xAI, trạng thái SSO và tự động bù acc' },
    'requests': { title: 'Quản Lý Request & IP Traffic', sub: 'Theo dõi chi tiết mọi HTTP Request, mã phản hồi 200, 404, 500 và IP kết nối' },
    'api-docs': { title: 'Tích Hợp API', sub: 'Tài liệu hướng dẫn kết nối chuẩn OpenAI cho bên thứ ba' }
  };

  if (headings[tabId]) {
    document.getElementById('tab-heading').innerText = headings[tabId].title;
    document.getElementById('tab-subheading').innerText = headings[tabId].sub;
  }

  // Tab specific reloads
  if (tabId === 'dashboard' || tabId === 'gallery') loadHistoryData();
  if (tabId === 'accounts') loadAccountsData();
  if (tabId === 'requests') loadRequestLogsData();
}

// ── Load All Data ──
async function loadAllData() {
  await Promise.all([loadStats(), loadModelsData(), loadHistoryData(), loadAccountsData(), loadRequestLogsData()]);
}

// ── Models Registry ──
async function loadModelsData() {
  try {
    const res = await fetch('/api/models');
    if (!res.ok) return;
    const data = await res.json();
    const select = document.getElementById('model-select');
    if (!select || !data.models) return;

    const imgModels = data.models.filter(m => m.type === 'image');
    const chatModels = data.models.filter(m => m.type === 'chat');

    let html = '';
    if (imgModels.length > 0) {
      html += `<optgroup label="🎨 Model Tạo Ảnh (Image Generation)">`;
      imgModels.forEach(m => {
        html += `<option value="${m.id}">${m.name} - [${m.badge}]</option>`;
      });
      html += `</optgroup>`;
    }
    if (chatModels.length > 0) {
      html += `<optgroup label="💬 Model Trò Chuyện & Suy Luận (Chat & Reasoning)">`;
      chatModels.forEach(m => {
        html += `<option value="${m.id}">${m.name} - [${m.badge}]</option>`;
      });
      html += `</optgroup>`;
    }
    select.innerHTML = html;
  } catch (err) {
    console.error('Lỗi tải models:', err);
  }
}

// ── Stats ──
async function loadStats() {
  try {
    const res = await fetch('/api/stats');
    if (!res.ok) return;
    const data = await res.json();

    document.getElementById('stat-total-accounts').innerText = data.total_accounts || '0';
    document.getElementById('stat-active-tokens').innerText = data.active_tokens || '0';
    document.getElementById('stat-total-images').innerText = data.success_images || '0';
    document.getElementById('stat-avg-speed').innerText = (data.avg_duration_seconds ? data.avg_duration_seconds + 's' : '15.2s');
    
    if (data.total_requests > 0) {
      const rate = Math.round((data.success_images / data.total_requests) * 100);
      document.getElementById('stat-success-rate').innerText = `${rate}% Thành công`;
    }
  } catch (err) {
    console.error('Lỗi tải stats:', err);
  }
}

// ── History & Gallery ──
async function loadHistoryData() {
  try {
    const res = await fetch('/api/history?limit=50');
    if (!res.ok) return;
    const rawItems = await res.json();
    const items = (rawItems || []).filter(i => i && i.url && i.status === 'success');

    renderRecentGallery(items.slice(0, 4));
    renderFullGallery(items);
  } catch (err) {
    console.error('Lỗi tải history:', err);
  }
}

function renderRecentGallery(items) {
  const container = document.getElementById('recent-gallery-grid');
  if (!items || items.length === 0) {
    container.innerHTML = `
      <div class="empty-state" style="grid-column: 1/-1; text-align: center; padding: 40px 0; color: #64748b;">
        <i class="fa-solid fa-image" style="font-size: 32px; margin-bottom: 8px;"></i>
        <p>Chưa có ảnh nào được tạo gần đây. Hãy vào Studio để tạo ảnh đầu tiên!</p>
      </div>`;
    return;
  }

  container.innerHTML = items.map(item => `
    <div class="gallery-card" onclick="openModal('${item.url}', '${escapeHtml(item.prompt)}')">
      <img src="${item.url}" alt="${escapeHtml(item.prompt)}" loading="lazy">
      <div class="gallery-card-info">
        <div class="gallery-card-prompt">${escapeHtml(item.prompt)}</div>
        <div class="gallery-card-date">
          <span>${item.created_at || ''}</span>
          <span>${item.duration ? item.duration + 's' : ''}</span>
        </div>
      </div>
    </div>
  `).join('');
}

function renderFullGallery(items) {
  const container = document.getElementById('full-gallery-grid');
  if (!items || items.length === 0) {
    container.innerHTML = `
      <div class="empty-state" style="grid-column: 1/-1; text-align: center; padding: 60px 0; color: #64748b;">
        <i class="fa-solid fa-images" style="font-size: 48px; margin-bottom: 12px;"></i>
        <p style="font-size: 16px; font-weight: 600;">Lịch sử tạo ảnh đang trống</p>
        <span>Hãy nhập prompt trong mục "Imagine Studio" để bắt đầu vẽ ảnh!</span>
      </div>`;
    return;
  }

  container.innerHTML = items.map(item => `
    <div class="gallery-card" onclick="openModal('${item.url}', '${escapeHtml(item.prompt)}')">
      <img src="${item.url}" alt="${escapeHtml(item.prompt)}" loading="lazy">
      <div class="gallery-card-info">
        <div class="gallery-card-prompt" title="${escapeHtml(item.prompt)}">${escapeHtml(item.prompt)}</div>
        <div class="gallery-card-date">
          <span><i class="fa-regular fa-clock"></i> ${item.created_at || ''}</span>
          <span>⚡ ${item.duration ? item.duration + 's' : ''}</span>
        </div>
      </div>
    </div>
  `).join('');
}

// ── Accounts Pool & Auto-Quota ──
async function loadAccountsData() {
  try {
    const res = await fetch('/api/pool');
    if (!res.ok) return;
    const data = await res.json();

    // Cập nhật thẻ thống kê Quota Pool
    document.getElementById('pool-stat-remaining').innerText = `${data.total_pool_remaining || 0} Ảnh`;
    document.getElementById('pool-stat-capacity').innerText = `${data.total_pool_capacity || 0} Ảnh`;
    document.getElementById('pool-stat-healthy').innerText = `${data.healthy_count || 0} Acc`;
    document.getElementById('pool-stat-utilization').innerText = `${data.utilization_pct || 0}% Đã Dùng`;
    document.getElementById('pool-stat-breakdown').innerText = `${data.healthy_count || 0} Khỏe | ${data.cooling_count || 0} Tạm Nghỉ | ${data.dead_count || 0} Chết`;

    const tbody = document.getElementById('accounts-tbody');
    if (!data.accounts || data.accounts.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: #64748b; padding: 30px;">Không có tài khoản nào trong Pool. Hãy bấm Auto Reg!</td></tr>`;
      return;
    }

    tbody.innerHTML = data.accounts.map((acc, idx) => {
      const maxQ = acc.max_quota || 25;
      const usedQ = acc.used_quota || 0;
      const remQ = acc.remaining_quota !== undefined ? acc.remaining_quota : Math.max(0, maxQ - usedQ);
      const percent = Math.round((remQ / maxQ) * 100);
      
      let barColor = '#00f5a0';
      if (percent < 25) barColor = '#f43f5e';
      else if (percent < 50) barColor = '#f59e0b';

      let statusBadge = '<span style="color: #00f5a0; font-weight: 700;"><i class="fa-solid fa-circle-check"></i> Sẵn Sàng</span>';
      if (acc.status === 'COOLING') {
        statusBadge = '<span style="color: #f59e0b; font-weight: 700;"><i class="fa-solid fa-clock"></i> Tạm Nghỉ (2h)</span>';
      } else if (acc.status === 'DEAD') {
        statusBadge = '<span style="color: #f43f5e; font-weight: 700;"><i class="fa-solid fa-circle-xmark"></i> Lỗi Token</span>';
      }

      return `
        <tr>
          <td><strong>#${idx + 1}</strong></td>
          <td><code>${escapeHtml(acc.email || '')}</code></td>
          <td><code>${escapeHtml(acc.password || '')}</code></td>
          <td><span class="badge-tag ${acc.type === 'Gmail' ? 'badge-gmail' : 'badge-mailtm'}">${acc.type || 'Mail.tm'}</span></td>
          <td>
            <div style="background: rgba(255,255,255,0.06); border-radius: 4px; height: 7px; overflow: hidden; margin-bottom: 4px; border: 1px solid rgba(255,255,255,0.1);">
              <div style="background: ${barColor}; width: ${percent}%; height: 100%; transition: width 0.3s;"></div>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 11px; color: ${barColor}; font-weight: 700;">
              <span>${remQ}/${maxQ} còn lại</span>
              <span>${percent}%</span>
            </div>
          </td>
          <td><strong style="color: #f0fdf4; font-family: 'JetBrains Mono', monospace;">${acc.total_success || 0}</strong></td>
          <td>${statusBadge}</td>
          <td>
            <button class="btn-copy-mini" onclick="copyText('${acc.email}')"><i class="fa-solid fa-copy"></i> Copy</button>
          </td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    console.error('Lỗi tải pool accounts:', err);
  }
}

async function syncPoolAccounts() {
  showToast('🔄 Đang đồng bộ danh sách tài khoản từ file...');
  try {
    const res = await fetch('/api/pool/sync', { method: 'POST' });
    const data = await res.json();
    showToast('✅ ' + data.message);
    loadAccountsData();
  } catch (err) {
    showToast('❌ Lỗi đồng bộ: ' + err.message);
  }
}

async function triggerHealthCheck() {
  const btn = document.getElementById('btn-health-check');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang Quét...';
  }
  showToast('🔍 Đang bắt đầu quét kiểm tra sức khỏe toàn bộ Pool...');
  try {
    const res = await fetch('/api/pool/health-check', { method: 'POST' });
    const data = await res.json();
    showToast('🩺 ' + (data.message || 'Quét sức khỏe hoàn tất!'));
    loadAccountsData();
  } catch (err) {
    showToast('❌ Lỗi quét sức khỏe: ' + err.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<i class="fa-solid fa-stethoscope"></i> Quét Sức Khỏe';
    }
  }
}

async function cleanDeadTokens() {
  if (!confirm('Bạn có chắc chắn muốn dọn sạch toàn bộ Token chết/hết hạn ra khỏi Pool không?')) return;
  const btn = document.getElementById('btn-clean-dead');
  if (btn) btn.disabled = true;
  showToast('🧹 Đang dọn dẹp các token chết...');
  try {
    const res = await fetch('/api/pool/clean-dead', { method: 'POST' });
    const data = await res.json();
    showToast('✨ ' + (data.message || 'Đã dọn sạch token chết!'));
    loadAccountsData();
  } catch (err) {
    showToast('❌ Lỗi dọn dẹp: ' + err.message);
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function triggerKeepAlive() {
  const btn = document.getElementById('btn-keep-alive');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang Nuôi...';
  }
  showToast('💓 Đang gửi tín hiệu Keep-Alive gia hạn session cookie...');
  try {
    const res = await fetch('/api/pool/keep-alive', { method: 'POST' });
    const data = await res.json();
    showToast('🌟 ' + (data.message || 'Đã gia hạn session thành công!'));
    loadAccountsData();
  } catch (err) {
    showToast('❌ Lỗi nuôi session: ' + err.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<i class="fa-solid fa-heart-pulse"></i> Nuôi Session (Keep-Alive)';
    }
  }
}

async function triggerAutoRelogin() {
  const btn = document.getElementById('btn-relogin');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang Login...';
  }
  showToast('🔑 Đang tự động đăng nhập lại các nick cũ để lấy Session SSO mới...');
  try {
    const res = await fetch('/api/pool/auto-relogin', { method: 'POST' });
    const data = await res.json();
    showToast('🎉 ' + (data.message || 'Đã hoàn tất đăng nhập lại!'));
    loadAccountsData();
  } catch (err) {
    showToast('❌ Lỗi đăng nhập lại: ' + err.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<i class="fa-solid fa-key"></i> Re-login Lấy Token Mới';
    }
  }
}

async function resetAllQuotas() {
  if (!confirm('Bạn có chắc muốn reset lại Quota của tất cả các tài khoản về 100% không?')) return;
  try {
    const res = await fetch('/api/pool/reset-all', { method: 'POST' });
    const data = await res.json();
    showToast('✅ ' + data.message);
    loadAccountsData();
  } catch (err) {
    showToast('❌ Lỗi reset quota: ' + err.message);
  }
}

// ── Auto Reg Trigger ──
async function triggerAutoReg() {
  const countInp = document.getElementById('reg-count-input');
  let count = parseInt(countInp ? countInp.value : '3', 10);
  if (isNaN(count) || count < 1) count = 1;
  if (count > 50) count = 50;

  const btn = document.getElementById('btn-reg-accounts');
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Đang Reg ${count} Nick...`;
  }

  showToast(`🚀 Đang bắt đầu tạo tự động ${count} nick mới trong nền...`);
  try {
    const res = await fetch(`/api/reg?count=${count}`, { method: 'POST' });
    const data = await res.json();
    showToast('✅ ' + data.message);
    setTimeout(() => {
      loadStats();
      loadAccountsData();
    }, 10000);
  } catch (err) {
    showToast('❌ Lỗi kích hoạt reg: ' + err.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<i class="fa-solid fa-plus"></i> Auto Reg`;
    }
  }
}

// ── Studio Image Generator ──
function initStudioForm() {
  const form = document.getElementById('studio-form');
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const promptInput = document.getElementById('prompt-input');
    const prompt = promptInput.value.trim();
    if (!prompt) return;

    const btn = document.getElementById('btn-generate');
    const stage = document.getElementById('preview-stage');

    btn.disabled = true;
    btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Đang yêu cầu Grok vẽ ảnh...`;

    let secondsElapsed = 0;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 120000);

    stage.innerHTML = `
      <div class="loading-spinner">
        <div class="spinner-icon"></div>
        <p style="font-weight: 700; color: #00f5a0; font-size: 16px;">Đang xử lý tạo ảnh qua Grok FLUX.1...</p>
        <span id="render-timer-text" style="font-size: 14px; color: #a7f3d0; font-family: 'JetBrains Mono', monospace; font-weight: 600;">⏱️ Đang vẽ: 0s / ~25s</span>
        <div style="font-size: 12px; color: #64748b; margin-top: 6px;">(FLUX.1 GPU đang render chi tiết 1024x1024 HD)</div>
      </div>`;

    const timerInterval = setInterval(() => {
      secondsElapsed++;
      const timerEl = document.getElementById('render-timer-text');
      if (timerEl) {
        timerEl.innerText = `⏱️ Đang vẽ: ${secondsElapsed}s / ~25s`;
      }
    }, 1000);

    try {
      const model = document.getElementById('model-select')?.value || 'grok-imagine-image-2.0';
      const res = await fetch('/api/draw', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: prompt, model: model }),
        signal: controller.signal
      });

      clearTimeout(timeoutId);

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Tạo ảnh thất bại');
      }

      const data = await res.json();
      if (data && data.url) {
        stage.innerHTML = `
          <div class="preview-image-result">
            <img src="${data.url}" alt="${escapeHtml(prompt)}" referrerpolicy="no-referrer">
            <div class="preview-image-actions">
              <a href="${data.url}" target="_blank" download class="btn btn-primary btn-block"><i class="fa-solid fa-download"></i> Tải Ảnh HD</a>
              <button type="button" class="btn btn-secondary" onclick="copyText('${window.location.origin}${data.url}')"><i class="fa-solid fa-link"></i> Copy Link</button>
            </div>
          </div>`;
        showToast(`🎉 Tạo ảnh thành công trong ${secondsElapsed}s!`);
        loadStats();
        loadHistoryData();
      } else {
        throw new Error('Không nhận được link ảnh');
      }
    } catch (err) {
      clearTimeout(timeoutId);
      const isTimeout = err.name === 'AbortError';
      const msg = isTimeout ? 'Yêu cầu tạo ảnh quá thời gian chờ (Timeout). Vui lòng thử lại.' : err.message;
      stage.innerHTML = `
        <div class="preview-placeholder" style="color: #f43f5e;">
          <i class="fa-solid fa-triangle-exclamation" style="color: #f43f5e; opacity: 1;"></i>
          <p>Có lỗi xảy ra khi tạo ảnh</p>
          <span>${escapeHtml(msg)}</span>
        </div>`;
      showToast('❌ ' + msg);
    } finally {
      clearInterval(timerInterval);
      clearTimeout(timeoutId);
      btn.disabled = false;
      btn.innerHTML = `<i class="fa-solid fa-sparkles"></i> Bắt Đầu Vẽ Ảnh`;
    }
  });
}

function setPrompt(text) {
  const input = document.getElementById('prompt-input');
  if (input) {
    input.value = text;
    input.focus();
  }
}

// ── Modal Viewer ──
function openModal(imgUrl, prompt) {
  const modal = document.getElementById('image-modal');
  const img = document.getElementById('modal-img');
  const promptEl = document.getElementById('modal-prompt');
  const downloadBtn = document.getElementById('modal-download');
  const copyBtn = document.getElementById('modal-copy-link');

  img.src = imgUrl;
  promptEl.innerText = prompt;
  downloadBtn.href = imgUrl;
  copyBtn.onclick = () => copyText(imgUrl);

  modal.classList.add('active');
}

function closeModal() {
  document.getElementById('image-modal').classList.remove('active');
}

// ── Request Logs & Traffic Analytics ──
let allRequestLogs = [];

async function loadRequestLogsData() {
  try {
    const [statsRes, logsRes] = await Promise.all([
      fetch('/api/request-stats'),
      fetch('/api/request-logs?limit=150')
    ]);

    if (statsRes.ok) {
      const stats = await statsRes.json();
      document.getElementById('req-stat-200').innerText = stats.status_2xx || '0';
      document.getElementById('req-stat-404').innerText = stats.status_404 || '0';
      document.getElementById('req-stat-errors').innerText = (stats.status_4xx_other || 0) + (stats.status_5xx || 0);
      document.getElementById('req-stat-ips').innerText = stats.unique_ips_count || '0';
    }

    if (logsRes.ok) {
      const data = await logsRes.json();
      allRequestLogs = data.logs || [];
      filterRequestLogs();
    }
  } catch (err) {
    console.error('Lỗi tải request logs:', err);
  }
}

function filterRequestLogs() {
  const statusFilter = document.getElementById('req-status-filter')?.value || 'all';
  const searchTerm = (document.getElementById('req-search-input')?.value || '').toLowerCase().trim();

  let filtered = allRequestLogs;

  if (statusFilter !== 'all') {
    if (statusFilter === '2xx') {
      filtered = filtered.filter(l => l.status_code >= 200 && l.status_code < 300);
    } else if (statusFilter === '404') {
      filtered = filtered.filter(l => l.status_code === 404);
    } else if (statusFilter === '4xx') {
      filtered = filtered.filter(l => l.status_code >= 400 && l.status_code < 500);
    } else if (statusFilter === '5xx') {
      filtered = filtered.filter(l => l.status_code >= 500);
    }
  }

  if (searchTerm) {
    filtered = filtered.filter(l => 
      (l.ip && l.ip.toLowerCase().includes(searchTerm)) ||
      (l.path && l.path.toLowerCase().includes(searchTerm)) ||
      (l.method && l.method.toLowerCase().includes(searchTerm)) ||
      (l.model && l.model.toLowerCase().includes(searchTerm)) ||
      (l.user_agent && l.user_agent.toLowerCase().includes(searchTerm))
    );
  }

  renderRequestLogs(filtered);
}

function renderRequestLogs(logs) {
  const tbody = document.getElementById('request-logs-tbody');
  if (!tbody) return;

  if (!logs || logs.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: #64748b; padding: 30px;">Chưa có request nào được ghi nhận.</td></tr>`;
    return;
  }

  tbody.innerHTML = logs.map((l) => {
    let badgeClass = 'badge-mailtm';
    let badgeColor = '#10b981';
    let code = l.status_code || 200;

    if (code >= 200 && code < 300) {
      badgeClass = 'badge-2xx';
      badgeColor = '#00f5a0';
    } else if (code === 404) {
      badgeClass = 'badge-404';
      badgeColor = '#f59e0b';
    } else if (code >= 400 && code < 500) {
      badgeClass = 'badge-4xx';
      badgeColor = '#fbbf24';
    } else if (code >= 500) {
      badgeClass = 'badge-5xx';
      badgeColor = '#f43f5e';
    }

    const methodColor = l.method === 'POST' ? '#38bdf8' : (l.method === 'GET' ? '#34d399' : '#a78bfa');

    let modelHtml = `<span style="color: #64748b; font-family: 'JetBrains Mono', monospace;">-</span>`;
    if (l.model && l.model !== '-' && l.model !== 'Dashboard' && l.model !== 'System / Pool') {
      modelHtml = `
        <span style="display: inline-flex; align-items: center; gap: 4px; font-family: 'JetBrains Mono', monospace; font-size: 11px; font-weight: 700; color: #38bdf8; background: rgba(56, 189, 248, 0.1); border: 1px solid rgba(56, 189, 248, 0.3); padding: 2px 7px; border-radius: 4px;">
          <i class="fa-solid fa-cube" style="font-size: 10px;"></i> ${escapeHtml(l.model)}
        </span>`;
    } else if (l.model === 'Dashboard' || l.model === 'System / Pool') {
      modelHtml = `
        <span style="font-family: 'JetBrains Mono', monospace; font-size: 11px; color: #94a3b8; background: rgba(148, 163, 184, 0.08); padding: 2px 6px; border-radius: 4px;">
          ${escapeHtml(l.model)}
        </span>`;
    }

    return `
      <tr>
        <td style="color: #94a3b8; font-size: 12px; white-space: nowrap;"><i class="fa-regular fa-clock"></i> ${l.timestamp || ''}</td>
        <td>
          <span style="font-family: 'JetBrains Mono', monospace; font-weight: 700; color: #f0fdf4; background: rgba(0,245,160,0.08); padding: 2px 8px; border-radius: 4px; border: 1px solid rgba(0,245,160,0.2);">
            <i class="fa-solid fa-location-dot" style="font-size: 10px; color: #00f5a0;"></i> ${escapeHtml(l.ip || '127.0.0.1')}
          </span>
        </td>
        <td><strong style="color: ${methodColor}; font-family: 'JetBrains Mono', monospace;">${l.method || 'GET'}</strong></td>
        <td><code style="color: #a7f3d0;">${escapeHtml(l.path || '/')}</code></td>
        <td>${modelHtml}</td>
        <td>
          <span style="font-weight: 800; font-family: 'JetBrains Mono', monospace; padding: 2px 8px; border-radius: 4px; color: ${badgeColor}; background: ${badgeColor}18; border: 1px solid ${badgeColor}40;">
            ${code}
          </span>
        </td>
        <td style="color: #6ee7b7; font-family: 'JetBrains Mono', monospace; font-size: 12px;">${l.duration_ms ? l.duration_ms + 'ms' : '< 1ms'}</td>
        <td style="color: #94a3b8; font-size: 11px; max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${escapeHtml(l.user_agent || '')}">
          ${escapeHtml(l.user_agent || 'Client')}
        </td>
      </tr>
    `;
  }).join('');
}

async function clearRequestLogs() {
  if (!confirm('Bạn có chắc chắn muốn xóa toàn bộ lịch sử log request?')) return;
  try {
    const res = await fetch('/api/request-logs/clear', { method: 'POST' });
    if (res.ok) {
      showToast('🗑️ Đã xóa sạch log request!');
      loadRequestLogsData();
    }
  } catch (err) {
    showToast('❌ Lỗi xóa log: ' + err.message);
  }
}

// ── Helpers ──
function showToast(msg) {
  const toast = document.getElementById('toast');
  toast.innerText = msg;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 3500);
}

function copyText(text) {
  navigator.clipboard.writeText(text);
  showToast('📋 Đã copy link vào bộ nhớ tạm!');
}

function copyCode(btn) {
  const pre = btn.previousElementSibling;
  if (pre) {
    const code = pre.querySelector('code')?.innerText || '';
    navigator.clipboard.writeText(code);
    showToast('📋 Đã copy đoạn mã!');
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
}

