/**
 * supervisor-common.js — Shared Supervisor Layout (Sidebar + Auth Guard)
 *
 * This file is loaded by every supervisor page. It:
 *  1. Defines GPNav.mount(activeKey) — the single call each page makes to:
 *       a) Verify the user is authenticated AND has the 'supervisor' role.
 *       b) Inject the sidebar CSS into <head> (only once per page load).
 *       c) Render the sidebar HTML into <aside id="supervisor-sidebar">.
 *       d) Set up avatar upload, logout button, and the unread notification badge.
 *  2. Exposes GPNav.updateUnreadBadge() so pages can refresh the badge after
 *     actions like marking a notification as read or booking a meeting.
 *
 * Usage in each supervisor HTML page:
 *   <script src="/static/supervisor-common.js"></script>
 *   <script>GPNav.mount('dashboard');</script>  ← pass the key matching one of LINKS
 */
(function (global) {

  // ── Navigation link definitions ─────────────────────────────────────────────
  /**
   * LINKS — ordered list of sidebar navigation items.
   * Each entry has:
   *   key   — unique identifier used by mount(activeKey) to highlight the current page
   *   href  — relative URL of the page (resolved from the server's root)
   *   label — human-readable link text shown in the sidebar
   *   icon  — Font Awesome class for the link's leading icon
   */
  const LINKS = [
    { key: 'dashboard',     href: '/Supervisor_dashboard.html',            label: 'Dashboard',            icon: 'fas fa-home' },
    { key: 'requests',      href: '/supervisor_student_requests.html',     label: 'Student Requests',     icon: 'fas fa-user-graduate' },
    { key: 'teams',         href: '/supervisor_my_teams.html',             label: 'My Teams',             icon: 'fas fa-users' },
    { key: 'schedule',      href: '/supervisor_schedule_discussions.html', label: 'Schedule Discussions', icon: 'fas fa-calendar-alt' },
    { key: 'grading',       href: '/supervisor_grading_reports.html',      label: 'Grading & Reports',    icon: 'fas fa-file-alt' },
    { key: 'files',         href: '/supervisor_files.html',                label: 'Project Files',        icon: 'fas fa-folder-open' },
    { key: 'notifications', href: '/supervisor_notifications.html',        label: 'Notifications',        icon: 'fas fa-bell' },
  ];


  // ── Sidebar CSS (injected once into <head>) ──────────────────────────────────
  /**
   * SIDEBAR_CSS — a <style> block injected into <head> by mount() on first call.
   *
   * Why inject CSS from JS instead of using styles.css?
   *   Each supervisor HTML page may load without styles.css (some pages embed their
   *   own inline styles). By injecting this block from supervisor-common.js we ensure
   *   every page that calls GPNav.mount() automatically gets the correct sidebar
   *   layout, regardless of which external stylesheets the page links to.
   *
   * What it styles:
   *   body                — flexbox row so sidebar and <main> sit side by side (LTR)
   *   #supervisor-sidebar — fixed 260 px wide dark-blue gradient column on the left
   *   .sv-profile         — avatar + name/role row at the top of the sidebar
   *   .sv-profile img     — circular avatar with a translucent white border
   *   .sv-name / .sv-role — display name (bold white) and role label (dim white)
   *   .side-nav           — flex column holding all navigation links
   *   .side-link          — individual nav anchor: icon + label, hover highlight
   *   .side-link.active   — same highlight applied to the current page's link
   *   .side-logout        — salmon/red text color for the logout link at the bottom
   *   .sv-badge           — small red pill showing the unread notification count
   *   main.main-content   — the page's scrollable content area to the right
   */
  const SIDEBAR_CSS = `
    <style id="sv-sidebar-css">
      /* Make body a flex row so sidebar + main-content sit side by side */
      body { display: flex; background: #f4f6fb; min-height: 100vh; margin: 0; font-family: 'Inter', sans-serif; }

      /* Fixed-width sidebar panel — dark blue gradient, full viewport height */
      #supervisor-sidebar {
        width: 260px; flex-shrink: 0;
        background: linear-gradient(180deg, #1e3c72, #2a5298);
        color: #fff; min-height: 100vh; padding: 30px 20px;
        display: flex; flex-direction: column;
      }

      /* Profile block — row with avatar image + name/role column */
      .sv-profile { display: flex; align-items: center; gap: 12px; margin-bottom: 40px; }

      /* Circular avatar thumbnail */
      .sv-profile img { width: 48px; height: 48px; border-radius: 50%; object-fit: cover; border: 2px solid rgba(255,255,255,.2); }

      /* Supervisor display name — bold white text */
      .sv-name { font-size: 0.95rem; font-weight: 700; color: #fff; }

      /* Role label below the name — slightly dim white */
      .sv-role { font-size: 0.78rem; color: rgba(255,255,255,.65); }

      /* Nav link column — stacks links vertically with small gap between them */
      .side-nav { display: flex; flex-direction: column; gap: 6px; flex: 1; }

      /* Individual nav link — icon + label, rounded hover state */
      .side-link {
        color: rgba(255,255,255,.85); text-decoration: none !important;
        padding: 12px 15px; border-radius: 8px;
        display: flex; align-items: center; gap: 10px;
        cursor: pointer; font-size: 0.875rem; transition: background 0.15s;
      }

      /* Fixed-width icon column so all labels align regardless of icon width */
      .side-link i { width: 16px; text-align: center; }

      /* Highlight on hover or when link matches the current page (active) */
      .side-link:hover, .side-link.active { background: rgba(255,255,255,.15); color: #fff; }

      /* Logout link — stands out in salmon/red to signal a destructive action */
      .side-logout { color: #ff8a80 !important; margin-top: 12px; }

      /* Notification count badge — red pill shown on the Notifications link */
      .sv-badge {
        min-width: 1.25rem; height: 1.25rem; padding: 0 0.3rem;
        border-radius: 999px; background: #ef4444; color: #fff;
        font-size: 0.7rem; display: none; align-items: center;
        justify-content: center; margin-left: auto;
      }

      /* Main content area — takes the remaining width, adds padding and scroll */
      main.main-content { flex: 1; padding: 30px 40px; overflow-x: auto; }
    </style>
  `;


  // ── Auth Guard ───────────────────────────────────────────────────────────────

  /**
   * requireSupervisor()
   * Verifies that the current browser session belongs to a logged-in supervisor.
   *
   * Checks:
   *  1. GPApi.getAccess() — there must be a JWT access token in localStorage.
   *  2. GPApi.getUser()   — there must be a cached user object in localStorage.
   *  3. user.role === 'supervisor' — only supervisors may view these pages.
   *
   * On any failure: redirects immediately to /login.html and returns null.
   * On success: returns the user object so mount() can display the user's name.
   *
   * @returns {object|null} User object if authenticated supervisor, null otherwise.
   */
  function requireSupervisor() {
    const u = global.GPApi.getUser();

    // Redirect if no token or no user info stored (not logged in)
    if (!global.GPApi.getAccess() || !u) { window.location.href = '/login.html'; return null; }

    // Redirect if the logged-in user is not a supervisor (e.g. a student)
    if (u.role !== 'supervisor')          { window.location.href = '/login.html'; return null; }

    return u; // user is authenticated and has the correct role
  }


  // ── Unread Badge ─────────────────────────────────────────────────────────────

  /**
   * updateUnreadBadge()
   * Fetches the current unread notification count from the backend and updates
   * the red badge pill next to the "Notifications" nav link in the sidebar.
   *
   * Called:
   *  - Once on every page load by mount().
   *  - After any action that may change the count (mark-read, delete, book meeting, etc.)
   *    by pages that call GPNav.updateUnreadBadge() directly.
   *
   * Behavior:
   *  - If count > 0: shows the badge with the number inside.
   *  - If count === 0: hides the badge element entirely.
   *  - If the API call fails: hides the badge silently (non-critical UI element).
   */
  async function updateUnreadBadge() {
    const el = document.getElementById('nav-unread-badge'); // the <span> inside the Notifications link
    if (!el) return; // sidebar may not be mounted yet — bail safely

    try {
      // GET /api/v1/supervisor/notifications/unread-count/ → { unread_count: N }
      const { unread_count } = await global.GPApi.notifUnreadCount();

      // Show the count (as a string) or clear it — then toggle visibility
      el.textContent = unread_count > 0 ? String(unread_count) : '';
      el.style.display = unread_count > 0 ? 'inline-flex' : 'none';
    } catch {
      // Silently hide on error — badge is decorative, not mission-critical
      el.style.display = 'none';
    }
  }


  // ── mount() — Main Entry Point ───────────────────────────────────────────────

  /**
   * mount(activeKey)
   * Called by every supervisor HTML page to initialise the shared sidebar.
   *
   * Steps performed in order:
   *  1. requireSupervisor() — redirects to /login.html if not authenticated.
   *  2. Inject SIDEBAR_CSS into <head> (skipped if already present).
   *  3. Render sidebar HTML into <aside id="supervisor-sidebar">.
   *  4. Wire up avatar click-to-upload behavior using a hidden <input type="file">.
   *  5. Wire up the Logout button (calls GPApi.logout() then redirects).
   *  6. Fetch and display the unread notification count badge.
   *
   * @param {string} activeKey - Key from LINKS (e.g. 'dashboard', 'teams').
   *                             The matching link gets the CSS class 'active'.
   */
  function mount(activeKey) {
    // Step 1 — Verify authentication; abort if not a supervisor
    const user = requireSupervisor();
    if (!user) return;

    // Step 2 — Inject sidebar CSS into <head> only once (id="sv-sidebar-css" guards re-injection)
    if (!document.getElementById('sv-sidebar-css')) {
      document.head.insertAdjacentHTML('beforeend', SIDEBAR_CSS);
    }

    // Find the <aside id="supervisor-sidebar"> placeholder in the page's HTML
    const root = document.getElementById('supervisor-sidebar');
    if (!root) return; // page doesn't have the sidebar placeholder — nothing to do

    // Determine the display name: prefer display_name, fall back to email
    const displayName = user.display_name || user.email;

    // Step 3a — If the page has a top-bar user pill, fill it with the display name
    const nameEl = document.getElementById('supervisor-user-name');
    if (nameEl) nameEl.textContent = displayName;

    // Step 3b — Choose the avatar source:
    //   - Priority 1: a Base64 image previously saved to localStorage by the upload handler
    //   - Priority 2: a generated initials avatar from ui-avatars.com (white on blue)
    const savedImg = localStorage.getItem('profileImg_' + user.email);
    const avatarSrc = savedImg ||
      `https://ui-avatars.com/api/?name=${encodeURIComponent(displayName)}&background=ffffff&color=1e3c72`;

    // Step 3c — Build the sidebar's inner HTML:
    //   - .sv-profile: clickable profile block (avatar + name + role) that triggers avatar upload
    //   - #sv-image-input: hidden file input; clicking the profile block opens it
    //   - .side-nav: the navigation link list; each link gets its icon, label, and 'active' class if it matches activeKey
    //   - Notifications link additionally gets the #nav-unread-badge <span> for the red count pill
    //   - #btn-logout: the logout anchor at the bottom of the nav
    root.innerHTML = `
      <div class="sv-profile">
        <img src="${avatarSrc}" alt="avatar" id="sv-avatar" />
        <div>
          <div class="sv-name">${displayName}</div>
          <div class="sv-role">Supervisor</div>
        </div>
      </div>

      <nav class="side-nav">
        ${LINKS.map((L) => `
          <a class="side-link ${L.key === activeKey ? 'active' : ''}" href="${L.href}">
            <i class="${L.icon}"></i>
            <span>${L.label}</span>
            ${L.key === 'notifications'
              ? '<span id="nav-unread-badge" class="sv-badge"></span>'
              : ''}
          </a>`).join('')}

        <!-- Logout link — styled red to distinguish it from regular nav items -->
        <a class="side-link side-logout" id="btn-logout">
          <i class="fas fa-sign-out-alt"></i>
          <span>Logout</span>
        </a>
      </nav>
    `;

    // ── Step 5 — Logout ────────────────────────────────────────────────────────
    // Clicking the Logout link calls GPApi.logout() which:
    //   1. POSTs /api/v1/auth/logout/ to blacklist the refresh token on the server
    //   2. Removes access, refresh, and user from localStorage
    // Then redirects the browser to the login page.
    document.getElementById('btn-logout').addEventListener('click', async () => {
      await global.GPApi.logout();
      window.location.href = '/login.html';
    });

    // ── Step 6 — Initial badge fetch ───────────────────────────────────────────
    // Fetch and display the unread notification count immediately after mounting
    updateUnreadBadge();
  }


  // ── Public API ───────────────────────────────────────────────────────────────
  /**
   * GPNav — the global object exposed to every supervisor page.
   *
   * Properties:
   *   mount(activeKey)      — call once per page to render the sidebar
   *   requireSupervisor()   — exported for pages that need the user object without mounting
   *   updateUnreadBadge()   — call after any action that changes the notification count
   *   LINKS                 — exported in case a page needs to iterate the nav structure
   */
  global.GPNav = { mount, requireSupervisor, updateUnreadBadge, LINKS };

})(window); // Pass window as 'global' so all exports land on window.GPNav
