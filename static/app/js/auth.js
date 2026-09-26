// Dectus — SaaS Portal Auth Controller
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
