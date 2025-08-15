// app/static/js/main.js
(function () {
  // --- CSRF helpers ---------------------------------------------------------
  function readCookie(name) {
    const m = document.cookie.match(new RegExp("(?:^|; )" + name.replace(/([.$?*|{}()[\]\\/+^])/g, "\\$1") + "=([^;]*)"));
    return m ? decodeURIComponent(m[1]) : "";
  }

  function getCSRF() {
    // 1) Prefer meta tag injected by base.html
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.content) return meta.content;

    // 2) Fall back to common cookie names
    //    - Flask-WTF often uses "csrf_token"
    //    - Some setups (e.g. axios defaults) use "XSRF-TOKEN"
    //    - JWT CSRF commonly uses "csrf_access_token"
    const candidates = ["csrf_token", "XSRF-TOKEN", "csrf_access_token"];
    for (const name of candidates) {
      const val = readCookie(name);
      if (val) return val;
    }
    return "";
  }

  async function apiFetch(url, opts = {}) {
    const headers = new Headers(opts.headers || {});
    const token = getCSRF();

    // Don’t set JSON content-type if body is FormData
    const isFormData = (opts.body && typeof FormData !== "undefined" && opts.body instanceof FormData);
    if (!isFormData && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }

    // Send CSRF using multiple common header names
    if (token) {
      if (!headers.has("X-CSRFToken"))   headers.set("X-CSRFToken", token);     // Flask-WTF / Django-style
      if (!headers.has("X-CSRF-Token"))  headers.set("X-CSRF-Token", token);    // Alt header name
      if (!headers.has("X-XSRF-TOKEN"))  headers.set("X-XSRF-TOKEN", token);    // Axios / some proxies
    }

    // Useful hint for server-side checks
    if (!headers.has("X-Requested-With")) headers.set("X-Requested-With", "XMLHttpRequest");

    const res = await fetch(url, { credentials: "same-origin", ...opts, headers });
    let data = null;
    try { data = await res.json(); } catch (e) { /* non-JSON */ }

    if (!res.ok || (data && data.ok === false)) {
      const msg = (data && (data.message || data.error)) || "Request failed.";
      throw new Error(msg);
    }
    return data || {};
  }

  function setBusy(el, busy) {
    if (!el) return;
    el.toggleAttribute("aria-busy", !!busy);
    el.disabled = !!busy;
    if (busy) el.dataset.busy = "1"; else delete el.dataset.busy;
  }

  // --- Likes (AJAX) ---------------------------------------------------------
  function initLikeButtons() {
    document.querySelectorAll("[data-like-btn]").forEach((btn) => {
      if (btn.dataset.bound === "1") return;
      btn.dataset.bound = "1";

      btn.addEventListener("click", async () => {
        if (btn.dataset.busy === "1") return;

        const postId = btn.dataset.postId;
        const countEl = document.querySelector(`[data-like-count="${postId}"]`);
        setBusy(btn, true);

        try {
          const data = await apiFetch(`/api/posts/${postId}/like`, {
            method: "POST",
            body: JSON.stringify({})
          });

          if (countEl) countEl.textContent = String(data.like_count);
          btn.setAttribute("aria-pressed", data.liked ? "true" : "false");
          const textSpan = btn.querySelector(".like-text");
          if (textSpan) textSpan.textContent = data.liked ? "Unlike" : "Like";
        } catch (e) {
          alert(e.message || "Sorry, could not update like right now.");
        } finally {
          setBusy(btn, false);
        }
      });
    });
  }

  // --- Comments (AJAX) ------------------------------------------------------
  function renderCommentLI(c) {
    const li = document.createElement("li");
    li.className = "comment-item";
    li.innerHTML = `
      <div class="avatar" aria-hidden="true">${(c.author_initial || "U").toUpperCase()}</div>
      <div class="comment-content">
        <div class="comment-head">
          <a class="comment-author" href="${c.author_url}">${c.author_username}</a>
          <span class="dot">•</span>
          <time class="comment-time">${c.date_human}</time>
        </div>
        <p class="comment-text"></p>
      </div>
    `;
    li.querySelector(".comment-text").textContent = c.content;
    return li;
  }

  function initCommentForms() {
    document.querySelectorAll("form[data-comment-form]").forEach((form) => {
      if (form.dataset.bound === "1") return;
      form.dataset.bound = "1";

      form.addEventListener("submit", async (ev) => {
        ev.preventDefault();
        if (form.dataset.busy === "1") return;

        const postId   = form.dataset.postId;
        const textarea = form.querySelector('textarea[name="content"]');
        const submit   = form.querySelector('[type="submit"]');
        const list     = document.querySelector(`[data-comments-list="${postId}"]`);
        const countEl  = document.querySelector(`[data-comment-count="${postId}"]`);
        const content  = (textarea?.value || "").trim();
        if (!content) return;

        setBusy(submit || form, true);
        try {
          const data = await apiFetch(`/api/posts/${postId}/comments`, {
            method: "POST",
            body: JSON.stringify({ content })
          });

          if (list && data.comment) {
            // Unhide the UL if it was hidden because there were 0 comments
            if (list.hasAttribute("hidden")) list.removeAttribute("hidden");
            list.appendChild(renderCommentLI(data.comment));
          }
          if (countEl && typeof data.comments_count === "number") {
            countEl.textContent = String(data.comments_count);
          }
          if (textarea) textarea.value = "";
        } catch (e) {
          alert(e.message || "Could not post your comment right now.");
        } finally {
          setBusy(submit || form, false);
        }
      });
    });
  }

  // --- Boot -----------------------------------------------------------------
  document.addEventListener("DOMContentLoaded", () => {
    initLikeButtons();
    initCommentForms();
  });
})();
