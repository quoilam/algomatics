(function(){
  const createBtn = document.getElementById('create-session');
  const sessionIdEl = document.getElementById('session-id');
  const sendBtn = document.getElementById('send');
  const clearBtn = document.getElementById('clear');
  const messages = document.getElementById('messages');
  const requestEl = document.getElementById('request');
  const imageEl = document.getElementById('image');
  const enableSearchEl = document.getElementById('enable-search');

  let sessionId = null;
  let pollingHandle = null;
  let lastLogCount = 0;

  function appendMessage(text, cls='bot'){
    const el = document.createElement('div');
    el.className = 'message '+(cls==='user'?'user':'bot');
    if(typeof text === 'string'){
      el.innerText = text;
    } else {
      el.appendChild(text);
    }
    messages.appendChild(el);
    messages.scrollTop = messages.scrollHeight;
  }

  function appendImageDataUri(uri){
    const img = document.createElement('img');
    img.src = uri;
    appendMessage(img, 'bot');
  }

  createBtn.addEventListener('click', async ()=>{
    try{
      const res = await fetch('/api/session/create', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({user_id:'web'}) });
      const data = await res.json();
      if(data.success){
        sessionId = data.session_id;
        sessionIdEl.innerText = '会话: ' + sessionId;
      } else {
        sessionIdEl.innerText = '创建失败';
      }
    }catch(e){
      sessionIdEl.innerText = '错误';
    }
  });

  sendBtn.addEventListener('click', async ()=>{
    const text = requestEl.value.trim();
    const file = imageEl.files[0];
    if(!text && !file) return;
    appendMessage(text || '[图片上传]', 'user');
    requestEl.value = '';

    try{
      let body, opts;
      if(file){
        body = new FormData();
        body.append('image', file);
        body.append('request', text);
        body.append('session_id', sessionId || '');
        body.append('enable_search', enableSearchEl.checked ? 'true' : 'false');
        opts = { method: 'POST', body };
      } else {
        body = { session_id: sessionId || '', request: text, enable_search: enableSearchEl.checked };
        opts = { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body) };
      }
      const resp = await fetch('/api/process', opts);
      const result = await resp.json();
      if(result.success){
        // 首次展示结果摘要（若有）
        if(result.text){ appendMessage(result.text, 'bot'); }

        // 开始轮询会话以获得实时步骤日志
        sessionId = result.session_id || sessionId;
        startPollingSession(sessionId);
      } else {
        appendMessage('后端处理失败: ' + (result.error||'未知错误'), 'bot');
      }
    }catch(e){
      appendMessage('请求出错: ' + e.message, 'bot');
    }
  });

  clearBtn.addEventListener('click', ()=>{ messages.innerHTML = ''; });

// ---------- polling and log rendering ----------
function startPollingSession(sessionId){
  if(!sessionId) return;
  if(pollingHandle) clearInterval(pollingHandle);
  lastLogCount = 0;
  const logsContainer = document.getElementById('logs-container');
  logsContainer.innerHTML = '';

  pollingHandle = setInterval(async ()=>{
    try{
      const res = await fetch('/api/session/' + sessionId);
      const data = await res.json();
      if(data && data.state_logs){
        // append newly arrived logs
        const logs = data.state_logs;
        for(let i=lastLogCount;i<logs.length;i++){
          renderLogEntry(logs[i]);
        }
        lastLogCount = logs.length;

        // 如果后端返回图片 base64，展示到最后一个执行结果位置
        if(data.output_image_base64){
          appendMessage('生成了输出图片（见下方步骤日志）', 'bot');
          // 在日志中也会包含 output_path， renderLogEntry 已处理图片的展示
        }

        // 停止条件
        const terminalStates = ['completed','accepted','needs_review','error'];
        if(terminalStates.includes(data.status)){
          clearInterval(pollingHandle);
          pollingHandle = null;
        }
      }
    }catch(e){
      console.warn('polling error', e);
    }
  }, 900);
}

function renderLogEntry(log){
  const container = document.getElementById('logs-container');
  const entry = document.createElement('div');
  entry.className = 'log-entry';

  const header = document.createElement('div');
  header.className = 'log-header';
  const title = document.createElement('div');
  title.className = 'log-title';
  title.innerText = `${log.agent} — ${log.action}`;
  const meta = document.createElement('div');
  meta.className = 'log-meta';
  meta.innerText = `${new Date(log.timestamp).toLocaleTimeString()} · ${log.status}`;
  header.appendChild(title);
  header.appendChild(meta);

  const body = document.createElement('div');
  body.className = 'log-body';

  // render data
  try{
    const data = log.data || {};
    // pretty print JSON-like fields
    Object.keys(data).forEach(k=>{
      const v = data[k];
      if(k.toLowerCase().includes('code') || k.toLowerCase().includes('preview') || k.toLowerCase().includes('improvement') || k.toLowerCase().includes('evaluation')){
        const pre = document.createElement('pre');
        pre.innerText = `${k}:\n${v}`;
        body.appendChild(pre);
      } else if(k.toLowerCase().includes('output_path') && v){
        const p = document.createElement('div');
        p.innerText = `输出路径: ${v}`;
        body.appendChild(p);
        // if v looks like a filename in output_images, try to display via session summary polling image
      } else {
        const p = document.createElement('div');
        p.innerText = `${k}: ${typeof v === 'string' ? v : JSON.stringify(v)}`;
        body.appendChild(p);
      }
    });
  }catch(e){
    const pre = document.createElement('pre'); pre.innerText = JSON.stringify(log.data||{}); body.appendChild(pre);
  }

  header.addEventListener('click', ()=>{ entry.classList.toggle('open'); });

  entry.appendChild(header);
  entry.appendChild(body);
  container.appendChild(entry);
  container.scrollTop = container.scrollHeight;
}

})();