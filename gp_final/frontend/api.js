/**
 * api.js — GP System Front-End API Client (JWT-based)
 *
 * This file is the ONLY place that talks to the backend REST API.
 * All supervisor and student pages import this via <script src="/static/api.js">.
 *
 * How it works:
 *  1. On login, the server returns an access token + refresh token (JWT).
 *  2. Both tokens are stored in localStorage.
 *  3. Every API request attaches the access token in the Authorization header.
 *  4. If the server returns 401 (token expired), the client automatically tries
 *     to get a new access token using the refresh token (tryRefresh).
 *  5. If the refresh also fails, the user must log in again.
 *
 * All API methods are attached to window.GPApi so every page can call them.
 */
(function (global) {

  // ── Base URL ────────────────────────────────────────────────────────────────
  // Builds the API base URL from the current page's origin so it works on
  // any host (localhost, production, etc.) without hardcoding a URL.
  const BASE = () => `https://gp2-graduation-backend.onrender.com/api/v1`;


  // ── Token & User helpers ────────────────────────────────────────────────────

  /** Returns the JWT access token stored in localStorage, or null if not logged in. */
  function getAccess() {
    return localStorage.getItem('access');
  }

  /** Returns the JWT refresh token stored in localStorage, or null if not logged in. */
  function getRefresh() {
    return localStorage.getItem('refresh');
  }

  /**
   * Saves one or both JWT tokens to localStorage.
   * Pass null for a token to skip saving it (e.g. when only refreshing the access token).
   * @param {string|null} access  - New access token.
   * @param {string|null} refresh - New refresh token.
   */
  function setTokens(access, refresh) {
    if (access)  localStorage.setItem('access',  access);
    if (refresh) localStorage.setItem('refresh', refresh);
  }

  /**
   * Removes all auth data from localStorage.
   * Called on logout or when authentication is no longer valid.
   */
  function clearAuth() {
    localStorage.removeItem('access');
    localStorage.removeItem('refresh');
    localStorage.removeItem('user');
  }

  /**
   * Returns the logged-in user object (parsed from localStorage), or null.
   * The user object contains: id, email, display_name, role, etc.
   */
  function getUser() {
    try {
      return JSON.parse(localStorage.getItem('user') || 'null');
    } catch {
      return null; // handles corrupt JSON in localStorage
    }
  }

  /**
   * Saves the user object to localStorage as a JSON string.
   * Called after login so pages can access user info without re-fetching the API.
   * @param {object} u - User object returned by the backend.
   */
  function setUser(u) {
    localStorage.setItem('user', JSON.stringify(u));
  }


  // ── Token Refresh ───────────────────────────────────────────────────────────

  /**
   * tryRefresh()
   * Attempts to obtain a new access token using the stored refresh token.
   * Called automatically by apiFetch when it receives a 401 response.
   * @returns {Promise<boolean>} true if a new access token was obtained, false otherwise.
   */
  async function tryRefresh() {
    const r = getRefresh();
    if (!r) return false; // no refresh token available — must log in again

    const res = await fetch(`${window.location.origin}/api/v1/auth/token/refresh/`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ refresh: r }),
    });

    if (!res.ok) return false; // refresh token is invalid or expired

    const data = await res.json();
    setTokens(data.access, null); // only save the new access token, keep the same refresh token
    return true;
  }


  // ── Core Fetch Wrapper ──────────────────────────────────────────────────────

  /**
   * apiFetch(path, opts)
   * The low-level fetch wrapper used by all API calls.
   *
   * What it does automatically:
   *  - Prepends the API base URL to the path.
   *  - Sets Content-Type: application/json (unless sending FormData).
   *  - Attaches the JWT access token in the Authorization header.
   *  - On 401 response: tries to refresh the token and retries the request once.
   *
   * @param {string}      path - API path, e.g. '/auth/login/'
   * @param {RequestInit} opts - Standard fetch options (method, body, headers, etc.)
   * @returns {Promise<Response>} Raw fetch Response object.
   */
  async function apiFetch(path, opts = {}) {
    const retried = opts._retried === true; // prevent infinite retry loop
    const clean   = { ...opts };
    delete clean._retried; // remove internal flag before passing to fetch

    // Build the full URL, handling paths that may or may not start with '/'
    const url     = `${BASE()}${path.startsWith('/') ? path : '/' + path}`;
    const headers = { ...(clean.headers || {}) };

    // Only set Content-Type to JSON when NOT sending a FormData (file upload)
    const isForm = clean.body instanceof FormData;
    if (!isForm && !headers['Content-Type']) {
      headers['Content-Type'] = 'application/json';
    }

    // Attach the Bearer token if the user is logged in
    const token = getAccess();
    if (token) headers['Authorization'] = `Bearer ${token}`;

    let res = await fetch(url, { ...clean, headers });

    // Auto-refresh: if 401 and we have a refresh token and haven't retried yet
    if (res.status === 401 && getRefresh() && !retried) {
      const ok = await tryRefresh();
      if (ok) {
        // Retry the original request with the new access token
        headers['Authorization'] = `Bearer ${getAccess()}`;
        res = await fetch(url, { ...clean, headers });
      }
    }

    return res;
  }


  // ── Auth Methods ────────────────────────────────────────────────────────────

  /**
   * login(email, password)
   * Authenticates the user with the backend.
   * On success: saves tokens and user object to localStorage.
   * On failure: throws an Error with the server's error message.
   * @returns {Promise<object>} The logged-in user object.
   */
  async function login(email, password) {
    const res  = await apiFetch('/auth/login/', {
      method: 'POST',
      body:   JSON.stringify({ email, password }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || data.detail || 'Login failed');
    setTokens(data.access, data.refresh); // store both tokens
    setUser(data.user);                   // cache user info locally
    return data.user;
  }

  /**
   * logout()
   * Blacklists the refresh token on the server (so it can't be reused),
   * then clears all auth data from localStorage.
   * Errors are silently ignored — the user is always logged out locally.
   */
  async function logout() {
    const refresh = getRefresh();
    if (refresh) {
      // Ask the server to invalidate this refresh token
      await apiFetch('/auth/logout/', {
        method: 'POST',
        body:   JSON.stringify({ refresh }),
      }).catch(() => {}); // ignore server errors — always clear local auth
    }
    clearAuth(); // remove tokens and user from localStorage
  }


  // ── JSON Helper ─────────────────────────────────────────────────────────────

  /**
   * getJson(path, opts)
   * Convenience wrapper around apiFetch that automatically:
   *  - Parses the JSON response body.
   *  - Throws a descriptive Error if the response is not OK (non-2xx).
   * Used by all API methods that expect a JSON response.
   * @returns {Promise<any>} Parsed JSON response data.
   */
  async function getJson(path, opts) {
    const res  = await apiFetch(path, opts);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || data.detail || JSON.stringify(data) || res.statusText);
    return data;
  }


  // ── Public API Object ───────────────────────────────────────────────────────
  // All methods below are attached to window.GPApi so every HTML page can use them.

  global.GPApi = {
    // Low-level utilities (needed by supervisor-common.js and pages)
    BASE,
    getAccess,    // check if user is logged in (returns token or null)
    getUser,      // get cached user object
    setUser,      // update cached user object
    clearAuth,    // clear all auth data
    apiFetch,     // raw fetch wrapper (used for DELETE calls that return 204)
    getJson,      // fetch + JSON parse + error throw

    // Auth
    login,        // POST /auth/login/
    logout,       // POST /auth/logout/ + clear localStorage

    // ── Teams ─────────────────────────────────────────────────────────────────
    // Returns all teams assigned to the current supervisor (or the student's team)
    teams: () => getJson('/teams/'),

    // Returns full detail for a single team by ID
    teamDetail: (id) => getJson(`/teams/${id}/`),

    // Returns the list of exam dates for a team (used to block scheduling)
    teamExamDates: (id) => getJson(`/teams/${id}/exam-dates/`),

    // Adds an exam date for a team — body: { date: 'YYYY-MM-DD' }
    addExamDate: (id, date) =>
      getJson(`/teams/${id}/exam-dates/`, { method: 'POST', body: JSON.stringify({ date }) }),

    // Supervisor sends a comment to all team members (creates notifications)
    teamComment: (id, comment) =>
      getJson(`/teams/${id}/comment/`, { method: 'POST', body: JSON.stringify({ comment }) }),

    // ── Supervisor: Supervision Requests ──────────────────────────────────────
    // Returns all pending supervision requests directed at the current supervisor
    requests: () => getJson('/supervisor/requests/'),

    // Approve or reject a request — body: { decision: 'approve' | 'reject' }
    decideRequest: (id, decision) =>
      getJson(`/supervisor/requests/${id}/decide/`, { method: 'POST', body: JSON.stringify({ decision }) }),

    // ── Supervisor: Availability Slots ────────────────────────────────────────
    // Returns all availability slots created by the current supervisor
    meetingSlots: () => getJson('/supervisor/slots/'),

    // Creates a new slot — body: { date, start_time, end_time, mode }
    addSlot: (body) => getJson('/supervisor/slots/', { method: 'POST', body: JSON.stringify(body) }),

    // Deletes a slot by ID — uses apiFetch directly because DELETE returns 204 (no body)
    deleteSlot: (id) =>
      apiFetch(`/supervisor/slots/${id}/`, { method: 'DELETE' }).then((r) => {
        if (!r.ok && r.status !== 204) return r.json().then((d) => Promise.reject(new Error(d.error || d.detail)));
        return null;
      }),

    // ── Supervisor: Meetings ──────────────────────────────────────────────────
    // Returns all meetings booked by the current supervisor
    meetings: () => getJson('/supervisor/meetings/'),

    // Books a meeting using the auto-slot algorithm — body: { team_id, meeting_type, topic }
    bookMeeting: (body) => getJson('/supervisor/meetings/book/', { method: 'POST', body: JSON.stringify(body) }),

    // ── Supervisor: Grading Reports ───────────────────────────────────────────
    // Returns all grading reports submitted by the current supervisor
    gradingList: () => getJson('/supervisor/grading/'),

    // Calculates a live final grade preview without saving — body: { chief_grade, examiner_one_grade, examiner_two_grade }
    gradingPreview: (body) => getJson('/supervisor/grading/preview/', { method: 'POST', body: JSON.stringify(body) }),

    // Saves a new grading report — body may include an archived file (multipart)
    gradingCreate: (body) => getJson('/supervisor/grading/', { method: 'POST', body: JSON.stringify(body) }),

    // ── Supervisor: Notifications ─────────────────────────────────────────────
    // Returns all notifications for the current user (newest first)
    notifications: () => getJson('/supervisor/notifications/'),

    // Returns { unread_count: N } — used to update the sidebar badge
    notifUnreadCount: () => getJson('/supervisor/notifications/unread-count/'),

    // Marks every unread notification as read in one request
    notifMarkAllRead: () => getJson('/supervisor/notifications/mark-all-read/', { method: 'POST', body: '{}' }),

    // Marks a single notification as read by ID — returns the updated notification
    notifMarkRead: (id) =>
      apiFetch(`/supervisor/notifications/${id}/read/`, { method: 'PATCH' }).then(async (r) => {
        const d = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(d.error || d.detail);
        return d;
      }),

    // Permanently deletes a notification by ID — returns 204 (no body)
    notifDelete: (id) =>
      apiFetch(`/supervisor/notifications/${id}/`, { method: 'DELETE' }).then((r) => {
        if (!r.ok && r.status !== 204) return r.json().then((x) => Promise.reject(new Error(x.error)));
        return null;
      }),

    // ── Supervisor: Team Files ────────────────────────────────────────────────
    // Returns files uploaded for the supervisor's teams; pass teamId to filter by one team
    files: (teamId) => {
      const q = teamId ? `?team_id=${encodeURIComponent(teamId)}` : '';
      return getJson(`/supervisor/files/${q}`);
    },

    // Permanently deletes a team file by ID (uploader or assigned supervisor only)
    deleteFile: (id) =>
      apiFetch(`/supervisor/files/${id}/`, { method: 'DELETE' }).then((r) => {
        if (!r.ok && r.status !== 204) return r.json().then((x) => Promise.reject(new Error(x.error)));
        return null;
      }),
  };

  // ── Compatibility layer for gp_system_v2 pages ──────────────────────────────
  global.getUser = GPApi.getUser;

  global.Auth = {
    requireRole: function(role) {
      const u = GPApi.getUser();
      if (!GPApi.getAccess() || !u || u.role !== role) {
        location.href = '/login.html';
      }
    },
    logout: async function() {
      await GPApi.logout();
      location.href = '/login.html';
    }
  };

  global.Teams = {
    list:    () => GPApi.getJson('/teams/'),
    myTeam: () => GPApi.getJson('/teams/').then(teams => {
      const u = GPApi.getUser();
      if (!u) return null;
      return teams.find(t => t.members.some(m => m.id === u.id)) || null;
    }).catch(() => null),

    create: (name, desc) => GPApi.getJson('/teams/', {
      method: 'POST',
      body: JSON.stringify({
        name,
        project_title: name,
        description: desc
      })
    }),

    sendJoinRequest: (id) =>
      GPApi.getJson(`/teams/${id}/join-requests/`, {
        method: 'POST',
        body: '{}'
      }),

    cancelJoinRequest: (id) =>
      GPApi.apiFetch(`/teams/${id}/join-requests/`, {
        method: 'DELETE'
      }),

    leave: (id) =>
      GPApi.apiFetch(`/teams/${id}/leave/`, {
        method: 'POST'
      }),

    getJoinRequests: (teamId) =>
      GPApi.getJson(`/teams/${teamId}/join-requests/`),

    getFiles: (teamId) =>
      GPApi.getJson(`/files/?team_id=${teamId}`).catch(() => []),

    getNotifications: () =>
      GPApi.getJson('/notifications/').catch(() => []),

    markRead: () =>
      GPApi.getJson('/notifications/mark-all-read/', {
        method: 'POST',
        body: '{}'
      }).catch(() => {}),

    vote: (reqId, vote, teamId) =>
      GPApi.getJson(`/teams/${teamId}/join-requests/${reqId}/decide/`, {
        method: 'POST',
        body: JSON.stringify({ decision: vote === 'yes' ? 'approve' : 'reject' })
      }),

    uploadFile: (teamId, formData) =>
      GPApi.apiFetch(`/files/`, {
        method: 'POST',
        body: formData
      }),

    supervisors: () =>
      GPApi.getJson('/auth/supervisors/'),

    getMeetings: () =>
      GPApi.getJson('/meetings/').catch(() => []),

    getSupervisorRequests: (teamId) =>
      GPApi.getJson(`/requests/?team_id=${teamId}`).catch(() => []),

    sendSupervisorRequest: (teamId, supId, priority) =>
      GPApi.getJson(`/requests/create/`, {
        method: 'POST',
        body: JSON.stringify({
          team_id: teamId,
          supervisor_id: supId,
          priority,
          project_idea: 'Graduation Project',
          preferences: [supId]
        })
      }),
};

  // ── Chat WebSocket ────────────────────────────────────────────
  global.TeamChat = class TeamChat {
    constructor(teamId, callbacks = {}) {
      this.teamId = teamId;
      this.cbs    = callbacks;
      this.ws     = null;
    }
    connect() {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws';
      const url   = `${proto}://${location.host}/ws/chat/${this.teamId}/?token=${getAccess()}`;
      this.ws = new WebSocket(url);
      this.ws.onopen    = ()  => this.cbs.onOpen?.();
      this.ws.onclose   = (e) => this.cbs.onClose?.(e);
      this.ws.onerror   = (e) => console.error('WS error', e);
      this.ws.onmessage = (e) => {
        const d = JSON.parse(e.data);
        if      (d.type === 'history') this.cbs.onHistory?.(d.messages);
        else if (d.type === 'message') this.cbs.onMessage?.(d);
        else if (d.type === 'edit')    this.cbs.onEdit?.(d);
        else if (d.type === 'delete')  this.cbs.onDelete?.(d);
      };
    }
    send(text)            { this._send({ type:'message', text }); }
    edit(id, text)        { this._send({ type:'edit', message_id:id, text }); }
    deleteForMe(id)       { this._send({ type:'delete_for_me', message_id:id }); }
    deleteForEveryone(id) { this._send({ type:'delete_for_everyone', message_id:id }); }
    close()               { this.ws?.close(); }
    _send(d) { if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(d)); }
  };

  // ── Notification WebSocket ────────────────────────────────────
  global.NotifSocket = class NotifSocket {
    constructor(callbacks = {}) {
      this.cbs = callbacks;
      this.ws  = null;
    }
    connect() {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws';
      const url   = `${proto}://${location.host}/ws/notifications/?token=${getAccess()}`;
      this.ws = new WebSocket(url);
      this.ws.onmessage = (e) => {
        const d = JSON.parse(e.data);
        if      (d.type === 'unread_count') this.cbs.onCount?.(d.count);
        else if (d.type === 'notification') this.cbs.onNotification?.(d);
      };
      this.ws.onclose = () => setTimeout(() => this.connect(), 4000);
    }
    markRead() {
      if (this.ws?.readyState === WebSocket.OPEN)
        this.ws.send(JSON.stringify({ type: 'mark_read' }));
    }
  };
// Attach to window in browsers, or globalThis in Node.js (for testing)
})(typeof window !== 'undefined' ? window : globalThis);
