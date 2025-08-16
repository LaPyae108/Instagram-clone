// app/static/js/main.js
(function () {
  // ---------- CSRF ----------
  function readCookie(name) {
    const m = document.cookie.match(
      new RegExp('(?:^|; )' + name.replace(/([.$?*|{}()[\]\\/+^])/g, '\\$1') + '=([^;]*)')
    );
    return m ? decodeURIComponent(m[1]) : '';
  }
  function getCSRF() {
    const meta = document.querySelector('meta[name="csrf-token"]');
    return (meta && meta.getAttribute('content')) || readCookie('csrf_token') || '';
  }

  async function apiFetch(url, opts = {}) {
    const headers = new Headers(opts.headers || {});
    const token = getCSRF();
    if (token) {
      if (!headers.has('X-CSRFToken')) headers.set('X-CSRFToken', token);
      if (!headers.has('X-CSRF-Token')) headers.set('X-CSRF-Token', token);
    }
    if (!headers.has('Content-Type')) headers.set('Content-Type', 'application/json');

    const res = await fetch(url, { credentials: 'same-origin', ...opts, headers });
    let data = null;
    try { data = await res.json(); } catch (_) {}
    if (!res.ok || (data && data.ok === false)) {
      const msg = (data && (data.message || data.error)) || 'Request failed.';
      throw new Error(msg);
    }
    return data || {};
  }

  function setBusy(el, busy) {
    el?.toggleAttribute('aria-busy', !!busy);
    if (el) el.disabled = !!busy;
    if (el && busy) el.dataset.busy = '1'; else if (el) delete el.dataset.busy;
  }

  // ---------- Cross-tab broadcast ----------
  function broadcast(payload) {
    try {
      localStorage.setItem('pw_update', JSON.stringify({ ...payload, ts: Date.now() }));
      // Clean up so the same page can receive the next event with the same values
      localStorage.removeItem('pw_update');
    } catch (_) {}
  }

  function applyUpdate(msg) {
    if (!msg || !msg.type) return;

    // Update like counter anywhere it appears
    if (msg.type === 'like') {
      const likeEls = document.querySelectorAll(`[data-like-count="${msg.postId}"]`);
      likeEls.forEach((el) => (el.textContent = String(msg.like_count)));
      // If a like button for this post exists on this page, reflect state
      document.querySelectorAll(`[data-like-btn][data-post-id="${msg.postId}"]`).forEach((btn) => {
        btn.setAttribute('aria-pressed', msg.liked ? 'true' : 'false');
        const t = btn.querySelector('.like-text');
        if (t) t.textContent = msg.liked ? 'Unlike' : 'Like';
      });
    }

    // Update comment counter anywhere it appears
    if (msg.type === 'comment') {
      const cEls = document.querySelectorAll(`[data-comment-count="${msg.postId}"]`);
      cEls.forEach((el) => (el.textContent = String(msg.comments_count)));
    }

    // Optional: reflect edits on Home cards (title/content)
    if (msg.type === 'post-edited') {
      const card = document.querySelector(`[data-post-card="${msg.postId}"]`);
      if (card) {
        const title = card.querySelector('[data-post-title]');
        const body = card.querySelector('[data-post-body]');
        if (title && typeof msg.title === 'string') title.textContent = msg.title;
        if (body && typeof msg.content === 'string') body.textContent = msg.content;
      }
    }
  }

  // Receive updates from other pages/tabs
  window.addEventListener('storage', (e) => {
    if (e.key !== 'pw_update' || !e.newValue) return;
    try { applyUpdate(JSON.parse(e.newValue)); } catch (_) {}
  });

  // ---------- Likes (AJAX) ----------
  function initLikeButtons() {
    document.querySelectorAll('[data-like-btn]').forEach((btn) => {
      if (btn.dataset.bound === '1') return;
      btn.dataset.bound = '1';

      btn.addEventListener('click', async () => {
        if (btn.dataset.busy === '1') return;
        const postId = btn.dataset.postId;
        const countEl = document.querySelector(`[data-like-count="${postId}"]`);
        setBusy(btn, true);
        try {
          const data = await apiFetch(`/api/posts/${postId}/like`, {
            method: 'POST',
            body: JSON.stringify({})
          });

          // Update this page
          if (countEl) countEl.textContent = String(data.like_count);
          btn.setAttribute('aria-pressed', data.liked ? 'true' : 'false');
          const textSpan = btn.querySelector('.like-text');
          if (textSpan) textSpan.textContent = data.liked ? 'Unlike' : 'Like';

          // Broadcast to other pages (e.g., Home)
          broadcast({ type: 'like', postId, like_count: data.like_count, liked: data.liked });
        } catch (e) {
          alert(e.message || 'Could not update like.');
        } finally {
          setBusy(btn, false);
        }
      });
    });
  }

  // ---------- Comments (AJAX) ----------
  function renderCommentLI(c) {
    const li = document.createElement('li');
    li.className = 'comment-item';
    li.innerHTML = `
      <div class="avatar" aria-hidden="true">${(c.author_initial || 'U').toUpperCase()}</div>
      <div class="comment-content">
        <div class="comment-head">
          <a class="comment-author" href="${c.author_url}">${c.author_username}</a>
          <span class="dot">•</span>
          <time class="comment-time">${c.date_human}</time>
        </div>
        <p class="comment-text"></p>
      </div>`;
    li.querySelector('.comment-text').textContent = c.content;
    return li;
  }

  function initCommentForms() {
    document.querySelectorAll('form[data-comment-form]').forEach((form) => {
      if (form.dataset.bound === '1') return;
      form.dataset.bound = '1';

      form.addEventListener('submit', async (ev) => {
        ev.preventDefault();
        if (form.dataset.busy === '1') return;

        const postId = form.dataset.postId;
        const textarea = form.querySelector('textarea[name="content"]');
        const submitBtn = form.querySelector('[type="submit"]');
        const list = document.querySelector(`[data-comments-list="${postId}"]`);
        const countEl = document.querySelector(`[data-comment-count="${postId}"]`);
        const content = (textarea?.value || '').trim();
        if (!content) return;

        setBusy(submitBtn || form, true);
        try {
          const data = await apiFetch(`/api/posts/${postId}/comments`, {
            method: 'POST',
            body: JSON.stringify({ content })
          });

          // Update this page
          if (data.comment && list) list.appendChild(renderCommentLI(data.comment));
          if (typeof data.comments_count === 'number' && countEl) {
            countEl.textContent = String(data.comments_count);
          }
          if (textarea) textarea.value = '';

          // Broadcast to Home
          broadcast({ type: 'comment', postId, comments_count: data.comments_count });
        } catch (e) {
          alert(e.message || 'Could not post your comment right now.');
        } finally {
          setBusy(submitBtn || form, false);
        }
      });
    });
  }

  // ---------- Back/forward cache fix ----------
  // If user returns to a page via back/forward cache, force a refresh so server data is fresh.
  window.addEventListener('pageshow', (e) => {
    if (e.persisted) window.location.reload();
  });

  // ---------- Boot ----------
  document.addEventListener('DOMContentLoaded', () => {
    initLikeButtons();
    initCommentForms();
  });
})();
