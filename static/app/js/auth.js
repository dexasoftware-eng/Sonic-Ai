// SonicSentinel AI — SaaS Portal Auth Controller
document.addEventListener('DOMContentLoaded', () => {
  // Password Visibility Toggle
  document.querySelectorAll('.password-toggle-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const input = btn.previousElementSibling;
      if (input.type === 'password') {
        input.type = 'text';
        btn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line></svg>`;
      } else {
        input.type = 'password';
        btn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>`;
      }
    });
  });

  // Handle Form Submissions
  const authForm = document.getElementById('portal-auth-form');
  const alertBox = document.getElementById('auth-alert');
  const submitBtn = document.getElementById('auth-submit-btn');
  const spinner = submitBtn ? submitBtn.querySelector('.spinner') : null;
  const btnText = submitBtn ? submitBtn.querySelector('.btn-text') : null;

  if (authForm) {
    authForm.addEventListener('submit', async (e) => {
      e.preventDefault();

      const endpoint = authForm.getAttribute('data-endpoint');
      const formData = new FormData(authForm);
      const dataObj = {};
      formData.forEach((val, key) => dataObj[key] = val);

      // UI Loading state
      if (alertBox) {
        alertBox.style.display = 'none';
        alertBox.className = 'auth-alert';
      }
      if (submitBtn) {
        submitBtn.disabled = true;
        if (spinner) spinner.style.display = 'inline-block';
        if (btnText) btnText.textContent = 'Authenticating...';
      }

      try {
        const response = await fetch(endpoint, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
          },
          body: JSON.stringify(dataObj)
        });

        const rawText = await response.text();
        let result = {};
        try {
          result = rawText ? JSON.parse(rawText) : {};
        } catch (jsonErr) {
          throw new Error('Server returned an unexpected response. Please try again in a moment.');
        }

        if (!response.ok || result.status === 'error') {
          throw new Error(result.detail || result.message || 'Authentication failed. Please check your credentials.');
        }

        // Success State
        if (result.session_token) {
          localStorage.setItem('portal_token', result.session_token);
        }
        if (result.user) {
          localStorage.setItem('portal_user', JSON.stringify(result.user));
        }

        if (alertBox) {
          alertBox.textContent = result.message || 'Access granted. Redirecting to your workspace...';
          alertBox.className = 'auth-alert success';
          alertBox.style.display = 'flex';
        }

        if (btnText) btnText.textContent = 'Redirecting...';

        // Ensure leading slash on redirect URL
        let targetUrl = result.redirect_url || '/app/user';
        if (!targetUrl.startsWith('/') && !targetUrl.startsWith('http')) {
          targetUrl = '/' + targetUrl;
        }
        setTimeout(() => {
          window.location.href = targetUrl;
        }, 650);

      } catch (err) {
        if (alertBox) {
          alertBox.textContent = err.message || 'Connection error. Please try again.';
          alertBox.className = 'auth-alert error';
          alertBox.style.display = 'flex';
        }
        if (submitBtn) {
          submitBtn.disabled = false;
          if (spinner) spinner.style.display = 'none';
          if (btnText) btnText.textContent = submitBtn.getAttribute('data-original-text') || 'Sign In';
        }
      }
    });
  }
});

/* ==========================================================================
   SONICSENTINEL AI CUSTOM TOAST & ALERT NOTIFICATION SYSTEM (AUTH)
   ========================================================================== */
(function() {
  function getOrCreateToastContainer() {
    let container = document.getElementById('dectus-toast-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'dectus-toast-container';
      container.className = 'dectus-toast-container';
      container.setAttribute('aria-live', 'polite');
      document.body.appendChild(container);
    }
    return container;
  }

  const ICONS = {
    success: '<i class="fa-solid fa-circle-check"></i>',
    copied: '<i class="fa-solid fa-clipboard-check"></i>',
    error: '<i class="fa-solid fa-circle-exclamation"></i>',
    danger: '<i class="fa-solid fa-circle-xmark"></i>',
    warning: '<i class="fa-solid fa-triangle-exclamation"></i>',
    info: '<i class="fa-solid fa-circle-info"></i>'
  };

  const DEFAULT_TITLES = {
    success: 'Success',
    copied: 'Copied to Clipboard',
    error: 'Action Failed',
    danger: 'Error Encountered',
    warning: 'Notice',
    info: 'Information'
  };

  function customAlert(message, type = 'info', title = null, duration = 3800) {
    if (!message) return;
    const container = getOrCreateToastContainer();
    const cleanType = String(type).toLowerCase().trim();
    const normalizedType = ['success', 'copied', 'error', 'danger', 'warning', 'info'].includes(cleanType) ? cleanType : 'info';

    const toast = document.createElement('div');
    toast.className = `dectus-toast toast-${normalizedType}`;
    toast.setAttribute('role', 'alert');

    const iconHtml = ICONS[normalizedType] || ICONS.info;
    const titleText = title || DEFAULT_TITLES[normalizedType] || 'Notification';

    toast.innerHTML = `
      <div class="dectus-toast-icon">${iconHtml}</div>
      <div class="dectus-toast-content">
        <div class="dectus-toast-title">${titleText}</div>
        <div class="dectus-toast-msg">${message}</div>
      </div>
      <button type="button" class="dectus-toast-close" aria-label="Dismiss">&times;</button>
      <div class="dectus-toast-progress">
        <div class="dectus-toast-progress-bar" style="animation-duration: ${duration}ms;"></div>
      </div>
    `;

    container.appendChild(toast);

    let dismissTimer = null;
    let isDismissed = false;

    function dismiss() {
      if (isDismissed) return;
      isDismissed = true;
      toast.classList.add('toast-dismissing');
      setTimeout(() => {
        if (toast.parentNode) toast.parentNode.removeChild(toast);
      }, 280);
    }

    const closeBtn = toast.querySelector('.dectus-toast-close');
    if (closeBtn) closeBtn.addEventListener('click', (e) => { e.stopPropagation(); dismiss(); });

    if (duration > 0) {
      dismissTimer = setTimeout(dismiss, duration);
      toast.addEventListener('mouseenter', () => {
        if (dismissTimer) clearTimeout(dismissTimer);
        const pBar = toast.querySelector('.dectus-toast-progress-bar');
        if (pBar) pBar.style.animationPlayState = 'paused';
      });
      toast.addEventListener('mouseleave', () => {
        const pBar = toast.querySelector('.dectus-toast-progress-bar');
        if (pBar) pBar.style.animationPlayState = 'running';
        dismissTimer = setTimeout(dismiss, 1200);
      });
    }

    return toast;
  }

  customAlert.success = (msg, title, duration) => customAlert(msg, 'success', title, duration);
  customAlert.copied = (msg, title, duration) => customAlert(msg || 'Copied to clipboard!', 'copied', title || 'Copied to Clipboard', duration);
  customAlert.error = (msg, title, duration) => customAlert(msg, 'error', title, duration);
  customAlert.warning = (msg, title, duration) => customAlert(msg, 'warning', title, duration);
  customAlert.info = (msg, title, duration) => customAlert(msg, 'info', title, duration);

  window.customAlert = customAlert;
  window.showToast = customAlert;
  window.showNotification = customAlert;

  window.alert = function(msg) {
    if (msg === undefined || msg === null) return;
    const strMsg = String(msg);
    if (strMsg.toLowerCase().includes('copied')) {
      customAlert.copied(strMsg);
    } else if (strMsg.toLowerCase().includes('error') || strMsg.toLowerCase().includes('failed') || strMsg.toLowerCase().includes('could not')) {
      customAlert.error(strMsg);
    } else if (strMsg.toLowerCase().includes('success') || strMsg.toLowerCase().includes('created') || strMsg.toLowerCase().includes('saved') || strMsg.toLowerCase().includes('deleted')) {
      customAlert.success(strMsg);
    } else {
      customAlert(strMsg, 'info');
    }
  };
})();
