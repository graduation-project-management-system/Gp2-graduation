/* ============================================
   GP Manager — Admin Panel JavaScript
   ============================================ */

/* ============================================
   DATA
   ============================================ */

const API_BASE_URL = window.location.origin;
const PROPOSALS_API_BASE = `${API_BASE_URL}/api/proposals/`;
const PROPOSALS_API_URL = `${API_BASE_URL}/api/proposals/`;
const PROPOSAL_CREATE_API_URL = `${API_BASE_URL}/api/proposals/create/`;
const TEAMS_API_URL = `${API_BASE_URL}/api/v1/teams/`;
const STUDENTS_API_URL = `${API_BASE_URL}/api/students/`;
const STUDENT_CREATE_API_URL = `${API_BASE_URL}/api/students/create/`;
const TEAM_CREATE_API_URL = `${API_BASE_URL}/api/v1/teams/`;
const SUPERVISORS_API_URL = `${API_BASE_URL}/api/v1/auth/supervisors/`;
const SUPERVISOR_CREATE_API_URL = `${API_BASE_URL}/api/v1/auth/supervisors/`;
const DEFENSE_API_URL = `${API_BASE_URL}/api/defense/`;
const GRADES_API_URL = `${API_BASE_URL}/api/grades/`;
const GRADE_CREATE_API_URL = `${API_BASE_URL}/api/grades/create/`;
const DASHBOARD_API_URL = `${API_BASE_URL}/api/dashboard/`;
const ACTIVITY_API_URL = `${API_BASE_URL}/api/activity/`;
const FILES_API_URL = `${API_BASE_URL}/api/v1/files/`;

/* Type config for activity */
const ACT_CONFIG = {
  upload:   { emoji: "📤", label: "Upload",     cls: "act-upload"   },
  approve:  { emoji: "✅", label: "Approved",   cls: "act-approve"  },
  reject:   { emoji: "❌", label: "Rejected",   cls: "act-reject"   },
  assign:   { emoji: "👤", label: "Assignment", cls: "act-assign"   },
  schedule: { emoji: "📅", label: "Scheduled",  cls: "act-schedule" },
  grade:    { emoji: "⭐", label: "Graded",     cls: "act-grade"    },
  team:     { emoji: "👥", label: "Team",       cls: "act-team"     },
};

/* Icon backgrounds */
const ICON_BG = {
  upload: "icon-upload", approve: "icon-approve", reject: "icon-reject",
  assign: "icon-assign", schedule: "icon-schedule", grade: "icon-grade", team: "icon-team",
};

/* ============================================
   STATE
   ============================================ */
let proposalFilter = "All";
let activityFilter = "All";
let gradeFilter = "All";
let proposalsState = [];
let teamsState = [];
let studentsState = [];
let supervisorsState = [];
let defenseState = [];
let activityState = [];
let gradesState = [];

let studentModalEditingId = null;
let pendingDeleteStudentId = null;
let supervisorModalEditingId = null;
let pendingDeleteSupervisorId = null;
let proposalModalEditingId = null;
let archivedTeamsState = [];
let pendingDeleteProposalId = null;
let teamModalEditingId = null;
let gradeModalEditingId = null;
let pendingDeleteGradeId = null;

const TEAM_MAX_MEMBERS = 5;
const SUPERVISOR_CAPACITY = 5;

function getSelectedTeamMemberIds(listId) {
    const container = document.getElementById(listId);
    if (!container) return [];
    return Array.from(container.querySelectorAll('input[type="checkbox"][name="team_member"]:checked'))
        .map((checkbox) => Number(checkbox.value));
}

function setTeamMembersError(errorId, message) {
    const el = document.getElementById(errorId);
    if (!el) return;
    if (message) {
        el.textContent = message;
        el.classList.add("show");
    } else {
        el.textContent = "";
        el.classList.remove("show");
    }
}

function updateTeamMembersSummary(listId, noteId, errorId) {
    const selectedIds = getSelectedTeamMemberIds(listId);
    const noteEl = document.getElementById(noteId);
    const container = document.getElementById(listId);
    if (noteEl) {
        noteEl.textContent = `${selectedIds.length} / ${TEAM_MAX_MEMBERS} selected.`;
    }
    if (container) {
        const checkboxes = Array.from(container.querySelectorAll('input[type="checkbox"][name="team_member"]'));
        const disableRemaining = selectedIds.length >= TEAM_MAX_MEMBERS;
        checkboxes.forEach((checkbox) => {
            if (!checkbox.checked) {
                checkbox.disabled = disableRemaining;
            } else {
                checkbox.disabled = false;
            }
        });
    }
    if (selectedIds.length > TEAM_MAX_MEMBERS) {
        setTeamMembersError(errorId, `Maximum team size is ${TEAM_MAX_MEMBERS} students.`);
    } else {
        setTeamMembersError(errorId, "");
    }
}

function handleTeamMembersToggle(event) {
    const container = event.currentTarget;
    if (!container) return;
    const listId = container.id;
    const errorId = listId === "add-team-members-list" ? "add-team-members-error" : "edit-team-members-error";
    const noteId = listId === "add-team-members-list" ? "add-team-members-note" : "edit-team-members-note";
    const selectedIds = getSelectedTeamMemberIds(listId);

    if (selectedIds.length > TEAM_MAX_MEMBERS) {
        event.target.checked = false;
        setTeamMembersError(errorId, `Maximum team size is ${TEAM_MAX_MEMBERS} students.`);
    } else {
        setTeamMembersError(errorId, "");
    }
    updateTeamMembersSummary(listId, noteId, errorId);
}

function renderTeamMembersList(listId, selectedIds = []) {
    const container = document.getElementById(listId);
    if (!container) return;

    const currentTeamId = listId === 'edit-team-members-list' ? teamModalEditingId : null;
    const rows = studentsState.map((student) => {
        const studentName = escapeHtml(student.name || student.display_name || student.email || `Student #${student.id}`);
        const checked = selectedIds.includes(student.id) ? "checked" : "";
        const assignedElsewhere = student.team_id != null && String(student.team_id) !== String(currentTeamId);
        const disabled = assignedElsewhere ? "disabled" : "";
        const tooltip = assignedElsewhere ? `title="Already assigned to ${escapeHtml(student.team || 'another team')}"` : "";
        return `
          <div class="team-member-row${assignedElsewhere ? ' disabled' : ''}">
            <label ${tooltip}>
              <input type="checkbox" name="team_member" value="${student.id}" ${checked} ${disabled} />
              <span class="team-member-name">${studentName}</span>
            </label>
          </div>
        `;
    });

    container.innerHTML = rows.join("") || `<div class="team-member-row empty">No students available.</div>`;
    container.removeEventListener("change", handleTeamMembersToggle);
    container.addEventListener("change", handleTeamMembersToggle);
    const errorId = listId === "add-team-members-list" ? "add-team-members-error" : "edit-team-members-error";
    const noteId = listId === "add-team-members-list" ? "add-team-members-note" : "edit-team-members-note";
    updateTeamMembersSummary(listId, noteId, errorId);
}

/* ============================================
   NAVIGATION
   ============================================ */

function authHeaders() {
    const token = localStorage.getItem('access');
    return {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
    };
}
// Auto-inject auth token to all fetch calls
const _origFetch = window.fetch;
window.fetch = function(url, opts = {}) {
    const token = localStorage.getItem('access');
    if (token && typeof url === 'string' &&
        (url.startsWith('/api/') || url.startsWith(window.location.origin + '/api/'))) {
        opts.headers = opts.headers || {};
        if (!opts.headers['Authorization']) {
            opts.headers['Authorization'] = `Bearer ${token}`;
        }
    }
    return _origFetch(url, opts);
};

function showSection(id, clickedEl) {
  // Hide all sections
  document.querySelectorAll(".section").forEach(s => s.classList.remove("active"));
  // Show target
  document.getElementById(id).classList.add("active");
  // Update nav
  document.querySelectorAll(".nav-item").forEach(n => n.classList.remove("active"));
  if (clickedEl) clickedEl.classList.add("active");
  if (id === "activity") void loadActivity();
  if (id === "archive") void loadArchive();
}

/* ============================================
   PROPOSALS
   ============================================ */
function renderProposals() {
  const search  = (document.getElementById("proposals-search")?.value || "").toLowerCase();
  const table   = document.getElementById("proposals-table");
  const tbody   = table?.querySelector("tbody") || document.getElementById("proposals-body");
  if (!tbody) return;

  const rows = proposalsState.filter(p => {
    const teamName = String(p.team_name || "").toLowerCase();
    const title = String(p.title || "").toLowerCase();
    const supervisor = String(p?.supervisor?.name || "").toLowerCase();
    const statusLabel = normalizeProposalStatus(p.status);
    const matchSearch = teamName.includes(search) || title.includes(search) || supervisor.includes(search);
    const matchFilter = proposalFilter === "All" || statusLabel === proposalFilter;
    return matchSearch && matchFilter;
  });
const newProposalsHTML = rows.length === 0
    ? `<tr><td colspan="7" style="text-align:center;padding:32px;color:#94a3b8;">No proposals found.</td></tr>`
    : rows.map(p => {
        const statusLabel = normalizeProposalStatus(p.status);
        const statusTag = {
          Approved: `<span class="tag green">Approved</span>`,
          Pending:  `<span class="tag amber">Pending</span>`,
          Rejected: `<span class="tag red">Rejected</span>`,
        }[statusLabel] || `<span class="tag gray">${p.status || "Unknown"}</span>`;

        const actionBtns = normalizeProposalStatus(p.status) === "Pending"
          ? `
            <button class="btn-approve" onclick="approveProposal(${p.id})">Approve</button>
            <button class="btn-reject"  onclick="rejectProposal(${p.id})">Reject</button>
          `
          : `<span style="color:#94a3b8;font-size:12px;">No actions</span>`;

        const fileName = String(p.file_name || "").trim();
        const fileUrl = String(p.file_url || "").trim();
        const fileCell = fileUrl
          ? `<a class="btn-view" href="${fileUrl}" target="_blank" rel="noopener">${escapeHtml(fileName || "View File")}</a>`
          : `<span style="color:#94a3b8;font-size:12px;">No file</span>`;

        return `
          <tr>
            <td><strong>${p.team_name || "-"}</strong></td>
            <td>${p.title || "-"}</td>
            <td>${fileCell}</td>
            <td>${escapeHtml(String(p?.supervisor?.name || "—"))}</td>
            <td>${formatSubmittedDate(p.submitted_at)}</td>
            <td>${statusTag}</td>
            <td>
              <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:6px">${actionBtns}</div>
              <div class="actions">
                <button class="action-btn" title="View File" onclick="viewProposalFile(${p.id})">👁</button>
                <button class="action-btn" title="Edit" onclick="editProposal(${p.id})">✏️</button>
                <button class="action-btn danger" title="Delete" onclick="confirmDeleteProposal(${p.id})">🗑</button>
              </div>
            </td>
          </tr>
        `;
      }).join("");

  if (tbody.innerHTML !== newProposalsHTML) tbody.innerHTML = newProposalsHTML;
  updateProposalCounts();
}

function normalizeProposalStatus(status) {
  const statusMap = {
    approved: "Approved",
    accepted: "Approved",
    rejected: "Rejected",
    pending: "Pending",
    submitted: "Pending",
    under_review: "Pending",
    draft: "Pending",
  };
  return statusMap[String(status || "").toLowerCase()] || "Pending";
}

function formatSubmittedDate(submittedAt) {
  if (!submittedAt) return "—";
  const date = new Date(submittedAt);
  if (Number.isNaN(date.getTime())) return submittedAt;
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

async function loadProposals() {
  try {
    const response = await fetch(PROPOSALS_API_BASE, { method: "GET" });
    if (!response.ok) throw new Error(`Failed to load proposals (${response.status})`);

    const data = await response.json();
    proposalsState = Array.isArray(data.proposals) ? data.proposals : [];
  } catch (error) {
    console.error("Error loading proposals:", error);
    proposalsState = [];
  } finally {
    renderProposals();
  }
}

function setProposalModalMode(mode) {
  const titleEl = document.getElementById("proposal-modal-title");
  const submitEl = document.getElementById("proposal-modal-submit-btn");
  const fileInput = document.getElementById("proposal-file-input");
  if (titleEl) titleEl.textContent = mode === "edit" ? "Edit Proposal" : "Add Proposal";
  if (submitEl) submitEl.textContent = mode === "edit" ? "Save Changes" : "Submit";
  if (fileInput) fileInput.required = mode !== "edit";
}

async function openProposalModal(proposal = null) {
  setModalError("add-proposal-error", "");

  const loads = [];
  if (!Array.isArray(teamsState) || teamsState.length === 0) loads.push(loadTeams());
  if (!Array.isArray(supervisorsState) || supervisorsState.length === 0) loads.push(loadSupervisors());
  if (loads.length) await Promise.all(loads);

  const teamSelect = document.getElementById("proposal-team-select");
  if (teamSelect) {
    teamSelect.innerHTML = [
      `<option value="" disabled selected>Unassigned</option>`,
      ...teamsState.map((t) => `<option value="${t.id}">${escapeHtml(String(t.name || `Team #${t.id}`))}</option>`),
    ].join("");
  }

  const supervisorSelect = document.getElementById("proposal-supervisor-select");
  if (supervisorSelect) {
    const options = supervisorsState.map((s) => {
     const label = getSupervisorFullName(s);
     const supervisorId = s.id;

     return supervisorId
       ? `<option value="${supervisorId}">${escapeHtml(label)}</option>`
       : "";
      }).filter(Boolean);
    supervisorSelect.innerHTML = [
      `<option value="" disabled selected>Choose a supervisor...</option>`,
      ...options,
    ].join("");
  }

  const form = document.getElementById("add-proposal-form");
  if (form) form.reset();

  if (proposal) {
    proposalModalEditingId = proposal.id;
    setProposalModalMode("edit");
    if (teamSelect) {
      teamSelect.value = String(proposal.team_id || "");
      teamSelect.disabled = true;
    }
    const titleInput = form?.querySelector('[name="title"]');
    if (titleInput) titleInput.value = String(proposal.title || "");
    if (supervisorSelect && proposal?.supervisor?.id != null) {
      supervisorSelect.value = String(proposal.supervisor.id);
    }
    const statusSelect = form?.querySelector('[name="status"]');
    if (statusSelect) statusSelect.value = normalizeProposalStatus(proposal.status).toLowerCase();
  } else {
    proposalModalEditingId = null;
    setProposalModalMode("add");
    if (teamSelect) teamSelect.disabled = false;
    const statusSelect = form?.querySelector('[name="status"]');
    if (statusSelect) statusSelect.value = "pending";
  }

  openModal("add-proposal-modal");
}

function isAllowedProposalFile(file) {
  if (!file || !file.name) return false;
  const lower = file.name.toLowerCase();
  return lower.endsWith(".pdf") || lower.endsWith(".doc") || lower.endsWith(".docx");
}

async function submitProposalForm(event) {
  event.preventDefault();
  setModalError("add-proposal-error", "");

  const form = event.currentTarget;
  const formData = new FormData(form);
  const isEdit = proposalModalEditingId != null;
  const selectedFile = formData.get("file");
  if (!isEdit && (!selectedFile || !selectedFile.name)) {
    setModalError("add-proposal-error", "Proposal file is required.");
    return;
  }
  if (selectedFile && selectedFile.name && !isAllowedProposalFile(selectedFile)) {
    setModalError("add-proposal-error", "Only PDF, DOC, and DOCX files are allowed.");
    return;
  }
  if (isEdit && (!selectedFile || !selectedFile.name)) formData.delete("file");

  const url = isEdit ? `${PROPOSALS_API_BASE}${proposalModalEditingId}/` : PROPOSAL_CREATE_API_URL;
  const method = isEdit ? "PUT" : "POST";

  try {
    const response = await fetch(url, {
      method,
      body: formData,
    });
    const data = await response.json().catch(() => null);

    console.log("PROPOSAL RESPONSE =", data);

         if (!response.ok || !data?.success) {
             throw new Error(JSON.stringify(data));
           }
    

    closeModal("add-proposal-modal");
    form.reset();
    proposalModalEditingId = null;
    setProposalModalMode("add");
    showUiFeedback(data.message || (isEdit ? "Proposal updated successfully." : "Proposal created successfully."));
    await Promise.all([loadProposals(), loadTeams(), loadDashboardStats()]);
  } catch (error) {
    console.error("[Proposals] Save failed", error);
    setModalError("add-proposal-error", error.message || "Failed to save proposal.");
  }
}

async function updateProposal(id, newStatus) {
  const actionPath = newStatus === "Approved" ? "approve/" : "reject/";
  const requestUrl = `${PROPOSALS_API_BASE}${id}/${actionPath}`;
  console.log(`[Proposals] Sending ${newStatus} request`, { id, url: requestUrl });
  try {
    const response = await fetch(requestUrl, {
      method: "POST",
    });
    console.log("[Proposals] Received response", { id, status: response.status, ok: response.ok });
    if (!response.ok) throw new Error(`Failed to update proposal (${response.status})`);
  } catch (error) {
    console.error("Error updating proposal:", error);
  } finally {
    await Promise.all([loadProposals(), loadDashboardStats()]);
  }
}

async function approveProposal(id) {
  console.log("[Proposals] Approve button clicked", { id });
  const proposal = proposalsState.find((p) => String(p.id) === String(id));
  if (!proposal) return;
  if (normalizeProposalStatus(proposal.status) !== "Pending") return;
  await updateProposal(id, "Approved");
}

async function rejectProposal(id) {
  console.log("[Proposals] Reject button clicked", { id });
  const proposal = proposalsState.find((p) => String(p.id) === String(id));
  if (!proposal) return;
  if (normalizeProposalStatus(proposal.status) !== "Pending") return;
  await updateProposal(id, "Rejected");
}

function updateProposalCounts() {
  const el = (id) => document.getElementById(id);
  if (el("pending-count"))  el("pending-count").textContent  = proposalsState.filter(p => normalizeProposalStatus(p.status) === "Pending").length;
  if (el("approved-count")) el("approved-count").textContent = proposalsState.filter(p => normalizeProposalStatus(p.status) === "Approved").length;
  if (el("rejected-count")) el("rejected-count").textContent = proposalsState.filter(p => normalizeProposalStatus(p.status) === "Rejected").length;
}

async function loadDashboardStats() {
  try {
    const [teamsRes, supervisorsRes, studentsRes, dashRes] = await Promise.all([
      fetch(TEAMS_API_URL).catch(() => null),
      fetch(SUPERVISORS_API_URL).catch(() => null),
      fetch(STUDENTS_API_URL).catch(() => null),
      fetch(DASHBOARD_API_URL).catch(() => null),
    ]);

    const set = (id, value) => {
      const el = document.getElementById(id);
      if (el && value != null) el.textContent = String(value);
    };

    const teamsData = teamsRes && teamsRes.ok ? await teamsRes.json().catch(() => []) : [];
    const normalizedTeams = (Array.isArray(teamsData) ? teamsData : []).map(t => ({
      ...t,
      supervisor_id: t.assigned_supervisor ? t.assigned_supervisor.id : null,
      members_count: Array.isArray(t.members) ? t.members.length : 0,
    }));

    const supervisorsData = supervisorsRes && supervisorsRes.ok ? await supervisorsRes.json().catch(() => []) : [];
    const normalizedSups = Array.isArray(supervisorsData)
      ? supervisorsData
      : (supervisorsData.supervisors || supervisorsData.results || []);

    const studentsData = studentsRes && studentsRes.ok ? await studentsRes.json().catch(() => ({})) : {};
    const normalizedStudents = Array.isArray(studentsData) ? studentsData : (studentsData.students || []);

    const dashData = dashRes && dashRes.ok ? await dashRes.json().catch(() => ({})) : {};

    // Use dashboard API counts (server-calculated) as primary source
    const totalStudents    = dashData.students    ?? normalizedStudents.length;
    const totalSupervisors = dashData.supervisors ?? normalizedSups.length;

    set("dashboard-total-teams",       normalizedTeams.length);
    set("dashboard-total-students",    totalStudents);
    set("dashboard-total-supervisors", totalSupervisors);
    set("dashboard-total-projects",    normalizedTeams.filter(t => t.project_title).length);
    set("dashboard-approved-proposals", normalizedTeams.filter(t => t.status === 'active' || t.status === 'approved').length);
    set("dashboard-pending-proposals",  normalizedTeams.filter(t => t.status === 'forming').length);
    set("dashboard-rejected-proposals", normalizedTeams.filter(t => t.status === 'rejected').length);
    set("dashboard-total-graded",   gradesState.filter(g => g.final_grade != null).length);
    set("dashboard-pending-grades", gradesState.filter(g => g.status === 'submitted').length);
    set("dashboard-class-average", "—");
    set("dashboard-top-grade",     "—");

    renderRecentActivities([]);
    renderPendingActions({
      pending_proposals:       normalizedTeams.filter(t => t.status === 'forming').length,
      pending_grades:          gradesState.filter(g => g.status === 'submitted').length,
      teams_without_supervisor: normalizedTeams.filter(t => !t.supervisor_id).length,
      teams_without_defense:   0,
      upcoming_defenses:       0,
    });

  } catch (error) {
    console.error("[Dashboard] Failed to load stats", error);
  }
}

function renderRecentActivities(activities) {
  const container = document.querySelector(".activity-list");
  if (!container) return;
  
  if (activities.length === 0) {
    container.innerHTML = '<li class="no-activity">No recent activity</li>';
    return;
  }
  
  container.innerHTML = activities.map(activity => {
    const initials = activity.created_by ? activity.created_by.charAt(0).toUpperCase() : 'S';
    const timeAgo = formatRelativeTime(activity.created_at);
    
    return `
      <li>
        <div class="av-circle">${initials}</div>
        <div><p>${escapeHtml(activity.description || activity.action)}</p><small>${timeAgo}</small></div>
      </li>
    `;
  }).join('');
}

function renderPendingActions(pending) {
  const container = document.querySelector(".pending-list");
  if (!container) return;
  
  const actions = [];
  
  if (pending.pending_proposals > 0) {
    actions.push({
      type: 'proposal',
      title: 'Proposal Review',
      description: `${pending.pending_proposals} proposals pending`,
      priority: 'high'
    });
  }
  
  if (pending.pending_grades > 0) {
    actions.push({
      type: 'grade',
      title: 'Grade Approval',
      description: `${pending.pending_grades} grades need approval`,
      priority: 'high'
    });
  }
  
  if (pending.teams_without_supervisor > 0) {
    actions.push({
      type: 'team',
      title: 'Supervisor Assignment',
      description: `${pending.teams_without_supervisor} teams without supervisor`,
      priority: 'medium'
    });
  }
  
  if (pending.teams_without_defense > 0) {
    actions.push({
      type: 'defense',
      title: 'Defense Scheduling',
      description: `${pending.teams_without_defense} teams need defense dates`,
      priority: 'medium'
    });
  }
  
  if (pending.upcoming_defenses > 0) {
    actions.push({
      type: 'defense',
      title: 'Upcoming Defense Sessions',
      description: `${pending.upcoming_defenses} defense sessions scheduled`,
      priority: 'low'
    });
  }
  
  // Update badge count
  const badge = document.querySelector(".badge");
  if (badge) badge.textContent = actions.length > 0 ? `${actions.length} items` : '0 items';
  
  if (actions.length === 0) {
    container.innerHTML = '<li class="no-pending">No pending actions</li>';
    return;
  }
  
  const priorityColors = {
    high: 'red',
    medium: 'amber',
    low: 'green'
  };
  
  container.innerHTML = actions.map(action => {
    const color = priorityColors[action.priority] || 'gray';
    return `
      <li><span class="dot ${color}"></span>
        <div><strong>${escapeHtml(action.title)}</strong><br><small>${escapeHtml(action.description)}</small></div>
        <span class="arrow">↗</span>
      </li>
    `;
  }).join('');
}

function formatRelativeTime(isoString) {
  if (!isoString) return 'Unknown time';
  
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now - date;
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);
  
  if (diffMins < 60) return `${diffMins} min ago`;
  if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
  if (diffDays < 7) return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
  return date.toLocaleDateString();
}

function filterProposals() { renderProposals(); }

function setProposalFilter(filter, btn) {
  proposalFilter = filter;
  document.querySelectorAll(".filter-btn").forEach(b => {
    if (b.closest("#proposals")) b.classList.remove("active");
  });
  btn.classList.add("active");
  renderProposals();
}

function viewProposalFile(id) {
  const proposal = proposalsState.find((p) => String(p.id) === String(id));
  if (!proposal) return;
  if (!proposal.file_url) {
    showUiFeedback("No uploaded file for this proposal.");
    return;
  }
  window.open(proposal.file_url, "_blank", "noopener");
}

function editProposal(id) {
  const proposal = proposalsState.find((p) => String(p.id) === String(id));
  if (!proposal) {
    showUiFeedback("Proposal not found. Please refresh and try again.");
    return;
  }
  openProposalModal(proposal);
}

function confirmDeleteProposal(id) {
  const proposal = proposalsState.find((p) => String(p.id) === String(id));
  if (!proposal) return;
  pendingDeleteProposalId = id;
  setModalError("delete-proposal-error", "");
  const titleEl = document.getElementById("delete-proposal-title");
  if (titleEl) titleEl.textContent = String(proposal.title || "this proposal");
  openModal("delete-proposal-modal");
}

async function deleteProposalConfirmed() {
  if (pendingDeleteProposalId == null) return;
  setModalError("delete-proposal-error", "");
  try {
    const response = await fetch(`${PROPOSALS_API_BASE}${pendingDeleteProposalId}/`, { method: "DELETE" });
    const data = await response.json().catch(() => null);
    if (!response.ok || !data?.success) {
      throw new Error(getJsonErrorMessage(data, `Failed to delete proposal (${response.status})`));
    }
    closeModal("delete-proposal-modal");
    pendingDeleteProposalId = null;
    showUiFeedback(data.message || "Proposal deleted successfully.");
    await Promise.all([loadProposals(), loadTeams(), loadDashboardStats()]);
  } catch (error) {
    console.error("[Proposals] Delete failed", error);
    setModalError("delete-proposal-error", error.message || "Failed to delete proposal.");
  }
}

/* ============================================
   SUPERVISORS
   ============================================ */
function renderSupervisors() {
  const grid = document.getElementById("supervisor-grid");
  if (!grid) return;
  const search = (document.getElementById("supervisors-search")?.value || "").toLowerCase();

  const filtered = supervisorsState.filter((s) => {
    const name = getSupervisorFullName(s).toLowerCase();
    const department = String(s?.department || "").toLowerCase();
    const email = String(s?.user?.email || "").toLowerCase();
    return name.includes(search) || department.includes(search) || email.includes(search);
  });

  grid.innerHTML = filtered.length === 0
    ? `<div style="text-align:center;padding:32px;color:#94a3b8">No supervisors found.</div>`
    : filtered.map(s => {
    const fullName = getSupervisorFullName(s);
    const initials = fullName
      .split(/\s+/)
      .filter(Boolean)
      .map(w => w[0])
      .join("")
      .slice(0, 2)
      .toUpperCase();

    const assigned = Number(s.assigned_count || 0);
    const capacity = Number(s.capacity || 0);
    const ratio = `${assigned} / ${capacity} teams`;
    const atCapacity = capacity > 0 && assigned >= capacity;
    const availabilityTag = atCapacity
      ? `<span class="tag red">Full Capacity</span>`
      : `<span class="tag green">Available</span>`;

    const email = String(s?.user?.email || "—");
    const dept = String(s?.department || "—");
    const teams = Array.isArray(s.teams) ? s.teams : [];
    const teamsHtml = teams.length
      ? teams.map(t => `<span class="sup-team-tag">👥 ${t.name}</span>`).join("")
      : `<span style="color:#94a3b8;font-size:12px;font-style:italic">No teams assigned</span>`;

    return `
      <div class="supervisor-card">
        <div class="sup-header">
          <div class="sup-avatar">${initials}</div>
          <div class="sup-info">
            <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap">
              <div class="sup-name">${fullName}</div>
              ${availabilityTag}
            </div>
            <div class="sup-dept">${dept}</div>
            <div class="sup-email">✉ ${email}</div>
          </div>
        </div>
        <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;margin-top:10px">
          <span style="font-size:12px;color:#64748b">Capacity Usage</span>
          <span class="tag blue">${ratio}</span>
        </div>
        <div class="sup-teams">${teamsHtml}</div>
        <div class="actions" style="margin-top:12px">
          <button class="action-btn" title="Edit" onclick="editSupervisor(${s.id})">✏️</button>
          <button class="action-btn danger" title="Delete" onclick="confirmDeleteSupervisor(${s.id})">🗑</button>
        </div>
      </div>
    `;
  }).join("");

  updateSupervisorStats();
  _populateExaminerSelects();
}

function _populateExaminerSelects() {
  const options = '<option value="">— None —</option>' +
    supervisorsState.map(s =>
      `<option value="${s.id}">${escapeHtml(getSupervisorFullName(s))}</option>`
    ).join('');
  ['schedule-examiner1-select','schedule-examiner2-select',
   'edit-examiner1-select','edit-examiner2-select'].forEach(id => {
    const el = document.getElementById(id);
    if (!el) return;
    const cur = el.value;
    el.innerHTML = options;
    if (cur) el.value = cur;
  });
}

async function loadSupervisors() {
  try {
    // Fetch supervisors and teams in parallel — don't rely on teamsState timing
    const [supRes, teamRes] = await Promise.all([
      fetch(SUPERVISORS_API_URL, { method: "GET" }),
      fetch(TEAMS_API_URL,       { method: "GET" }),
    ]);
    if (!supRes.ok) throw new Error(`Failed to load supervisors (${supRes.status})`);

    const supData  = await supRes.json();
    const teamData = teamRes.ok ? await teamRes.json().catch(() => []) : [];

    const raw   = Array.isArray(supData) ? supData : [];
    const teams = (Array.isArray(teamData) ? teamData : []).map(t => ({
      ...t,
      supervisor_id: t.assigned_supervisor ? t.assigned_supervisor.id : null,
    }));

    // Group teams by supervisor id
    const teamsBySup = {};
    teams.forEach(t => {
      if (t.supervisor_id) {
        (teamsBySup[t.supervisor_id] = teamsBySup[t.supervisor_id] || []).push(t);
      }
    });

    // Also update teamsState if it is empty (prevents stale data in other sections)
    if (!teamsState.length && teams.length) teamsState = teams;

    supervisorsState = raw.map(s => ({
      id: s.id,
      user: { first_name: s.display_name, last_name: '', email: s.email, username: s.display_name },
      department:     s.department || '—',
      capacity:       SUPERVISOR_CAPACITY,
      assigned_count: (teamsBySup[s.id] || []).length,
      teams:          (teamsBySup[s.id] || []).map(t => ({ id: t.id, name: t.name })),
    }));
  } catch (error) {
    console.error("[Supervisors] Error loading supervisors:", error);
    supervisorsState = [];
  } finally {
    renderSupervisors();
  }
}

function getSupervisorFullName(supervisor) {
  const firstName = String(supervisor?.user?.first_name || "").trim();
  const lastName = String(supervisor?.user?.last_name || "").trim();
  const fallbackName = String(supervisor?.user?.username || "Supervisor").trim();
  return `${firstName} ${lastName}`.trim() || fallbackName;
}

function isSupervisorFull(supervisor) {
  const capacity = Number(supervisor?.capacity || SUPERVISOR_CAPACITY);
  const assigned = Number(supervisor?.assigned_count || 0);
  return capacity > 0 && assigned >= capacity;
}

function supervisorOptionHtml(supervisor, currentSupervisorId = "") {
  const uid = supervisor?.id;
  if (uid == null) return "";
  const isCurrent = String(uid) === String(currentSupervisorId || "");
  const full = isSupervisorFull(supervisor);
  const label = `${getSupervisorFullName(supervisor)}${full ? " (Full)" : ""}`;
  const disabled = full && !isCurrent ? " disabled" : "";
  return `<option value="${uid}"${disabled}>${escapeHtml(label)}</option>`;
}

function filterSupervisors() {
  renderSupervisors();
}

function updateSupervisorStats() {
  const totalEl = document.getElementById("supervisors-total-count");
  const assignedEl = document.getElementById("supervisors-assigned-count");
  const availableEl = document.getElementById("supervisors-available-count");
  const unassignedTeamsEl = document.getElementById("supervisors-unassigned-teams-count");

  const total = supervisorsState.length;
  const assigned = supervisorsState.filter((s) => Number(s.assigned_count || 0) > 0).length;
  const available = supervisorsState.filter((s) => Number(s.capacity || 0) > Number(s.assigned_count || 0)).length;
  const unassignedTeams = teamsState.filter((t) => !t.supervisor_id).length;

  if (totalEl) totalEl.textContent = String(total);
  if (assignedEl) assignedEl.textContent = String(assigned);
  if (availableEl) availableEl.textContent = String(available);
  if (unassignedTeamsEl) unassignedTeamsEl.textContent = String(unassignedTeams);
}

function setSupervisorModalMode(mode) {
  const titleEl = document.querySelector("#add-supervisor-modal .modal-header h3");
  const submitBtn = document.getElementById("supervisor-modal-submit-btn");
  if (titleEl) titleEl.textContent = mode === "edit" ? "Edit Supervisor" : "Add Supervisor";
  if (submitBtn) submitBtn.textContent = mode === "edit" ? "Save Changes" : "Create Supervisor";
}

function fillSupervisorForm(supervisor) {
  const form = document.getElementById("add-supervisor-form");
  if (!form || !supervisor) return;

  const firstNameInput = form.querySelector('[name="first_name"]');
  const lastNameInput = form.querySelector('[name="last_name"]');
  const emailInput = form.querySelector('[name="email"]');
  const departmentInput = form.querySelector('[name="department"]');
  const capacityInput = form.querySelector('[name="capacity"]');

  if (firstNameInput) firstNameInput.value = String(supervisor?.user?.first_name || "");
  if (lastNameInput) lastNameInput.value = String(supervisor?.user?.last_name || "");
  if (emailInput) emailInput.value = String(supervisor?.user?.email || "");
  if (departmentInput) departmentInput.value = String(supervisor?.department || "");
  if (capacityInput) capacityInput.value = String(supervisor?.capacity ?? 0);
}

function openSupervisorModal(supervisor = null) {
  setModalError("add-supervisor-error", "");
  const form = document.getElementById("add-supervisor-form");

  if (form) form.reset();

  if (supervisor) {
    supervisorModalEditingId = supervisor.id;
    setSupervisorModalMode("edit");
    fillSupervisorForm(supervisor);
  } else {
    supervisorModalEditingId = null;
    setSupervisorModalMode("add");
  }
  openModal("add-supervisor-modal");
}

function editSupervisor(id) {
  const supervisor = supervisorsState.find((s) => String(s.id) === String(id));
  if (!supervisor) {
    showUiFeedback("Supervisor not found. Please refresh and try again.");
    return;
  }
  openSupervisorModal(supervisor);
}

function confirmDeleteSupervisor(id) {
  const supervisor = supervisorsState.find((s) => String(s.id) === String(id));
  if (!supervisor) return;
  pendingDeleteSupervisorId = id;
  setModalError("delete-supervisor-error", "");

  const nameEl = document.getElementById("delete-supervisor-name");
  if (nameEl) nameEl.textContent = getSupervisorFullName(supervisor);

  const warningEl = document.getElementById("delete-supervisor-warning");
  const canDelete = Number(supervisor.assigned_count || 0) === 0;
  if (warningEl) warningEl.style.display = canDelete ? "none" : "block";

  const confirmBtn = document.getElementById("btn-confirm-delete-supervisor");
  if (confirmBtn) confirmBtn.disabled = !canDelete;

  openModal("delete-supervisor-modal");
}

async function deleteSupervisorConfirmed() {
  if (pendingDeleteSupervisorId == null) return;
  setModalError("delete-supervisor-error", "");

  try {
    const response = await fetch(`${SUPERVISORS_API_URL}${pendingDeleteSupervisorId}/`, {
      method: "DELETE",
    });
    const data = await response.json().catch(() => null);
    if (!response.ok || !data?.success) {
      throw new Error(getJsonErrorMessage(data, `Failed to delete supervisor (${response.status})`));
    }
    closeModal("delete-supervisor-modal");
    pendingDeleteSupervisorId = null;
    showUiFeedback(data.message || "Supervisor deleted successfully.");
    await Promise.all([loadSupervisors(), loadTeams(), loadStudents(), loadProposals()]);
  } catch (error) {
    console.error("[Supervisors] Delete failed", error);
    setModalError("delete-supervisor-error", error.message || "Failed to delete supervisor.");
  }
}

/* ============================================
   STUDENTS
   ============================================ */
function syncStudentsTeamFilter() {
  const select = document.getElementById("students-team-filter");
  if (!select) return;
  const current = select.value || "All";

  const options = [
    `<option value="All">All Teams</option>`,
    ...teamsState.map((t) => `<option value="${escapeHtml(String(t.name || ""))}">${escapeHtml(String(t.name || ""))}</option>`),
  ];
  select.innerHTML = options.join("");

  // Restore previous selection if still available
  const hasCurrent = Array.from(select.options).some((o) => o.value === current);
  select.value = hasCurrent ? current : "All";
}

function updateStudentStats() {
  const totalEl = document.getElementById("students-total-count");
  const activeEl = document.getElementById("students-active-count");
  const pendingEl = document.getElementById("students-pending-count");
  const teamsCoveredEl = document.getElementById("students-teams-covered-count");

  const total = studentsState.length;
  const active = studentsState.filter((s) => s.status === "Active").length;
  const pending = studentsState.filter((s) => s.status === "Pending").length;
  const teamsCovered = new Set(
    studentsState
      .map((s) => s.team)
      .filter((name) => name && name !== "Unassigned" && name !== "-")
  ).size;

  if (totalEl) totalEl.textContent = String(total);
  if (activeEl) activeEl.textContent = String(active);
  if (pendingEl) pendingEl.textContent = String(pending);
  if (teamsCoveredEl) teamsCoveredEl.textContent = String(teamsCovered);
}

function escapeHtml(str) {
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderStudents() {
  const search  = (document.getElementById("students-search")?.value || "").toLowerCase();
  const team    = document.getElementById("students-team-filter")?.value || "All";
  const tbody   = document.getElementById("students-body");
  if (!tbody) return;

  const rows = studentsState.filter(s => {
    const matchSearch = s.name.toLowerCase().includes(search) || s.sid.includes(search);
    const matchTeam   = team === "All" || s.team === team;
    return matchSearch && matchTeam;
  });

  const newStudentsHTML = rows.length === 0
    ? `<tr><td colspan="7" style="text-align:center;padding:32px;color:#94a3b8;">No students found.</td></tr>`
    : rows.map(s => {
        const initials = s.name.split(" ").map(w => w[0]).join("").slice(0, 2);
        const statusTag = s.status === "Active"
          ? `<span class="tag green">Active</span>`
          : `<span class="tag amber">Pending</span>`;

        return `
          <tr>
            <td>
              <div style="display:flex;align-items:center;gap:10px">
                <div style="width:32px;height:32px;border-radius:50%;background:#eff6ff;color:#1e3a8a;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;flex-shrink:0">${initials}</div>
                <strong>${s.name}</strong>
              </div>
            </td>
            <td style="font-family:monospace;font-size:12px;color:#64748b">${s.sid}</td>
            <td>${s.team}</td>
            <td>${s.supervisor}</td>
            <td>${statusTag}</td>
            <td><strong>${s.gpa}</strong></td>
            <td class="actions">
              <button class="action-btn" title="Edit" onclick="editStudent(${s.id})">✏️</button>
              <button class="action-btn danger" title="Delete" onclick="confirmDeleteStudent(${s.id})">🗑</button>
            </td>
          </tr>
        `;
      }).join("");

  if (tbody.innerHTML !== newStudentsHTML) tbody.innerHTML = newStudentsHTML;
  updateStudentStats();
}

function filterStudents() { renderStudents(); }

async function loadStudents() {
  try {
    const response = await fetch(STUDENTS_API_URL, { method: "GET" });
    console.log("🔍 DEBUG: Students API response status:", response.status);
    console.log("🔍 DEBUG: Students API URL:", STUDENTS_API_URL);
    console.log("🔍 DEBUG: Students API ok:", response.ok);
    
    if (!response.ok) throw new Error(`Failed to load students (${response.status})`);
    const data = await response.json();
    console.log("🔍 DEBUG: Students API response data:", data);
    
    // API returns flat array of UserSerializer objects
    const students = Array.isArray(data) ? data : (Array.isArray(data.students) ? data.students : []);
    console.log("🔍 DEBUG: Extracted students array length:", students.length);
    
    studentsState = students.map((item) => ({
      id:          item.id,
      name:        item.name || item.display_name || "Unknown Student",
      sid:         item.sid  || item.email || "-",
      team_id:     item.team_id || null,
      team:        item.team || "—",
      supervisor_id: item.supervisor_id || null,
      supervisor:  item.supervisor || "—",
      status:      item.status || "Active",
      gpa:         item.gpa || "-",
    }));
    console.log("🔍 DEBUG: studentsState after mapping - length:", studentsState.length);
    if (studentsState.length > 0) console.log("🔍 DEBUG: First student in state:", studentsState[0]);
  } catch (error) {
    console.error("🔴 ERROR loading students:", error);
    console.error("🔴 ERROR message:", error.message);
    console.error("🔴 ERROR stack:", error.stack);
    studentsState = [];
  } finally {
    console.log("🔍 DEBUG: Final studentsState.length before render:", studentsState.length);
    syncStudentsTeamFilter();
    renderStudents();
  }
}

function setStudentModalMode(mode) {
  const titleEl = document.getElementById("student-modal-title");
  const submitEl = document.getElementById("student-modal-submit-btn");
  if (titleEl) titleEl.textContent = mode === "edit" ? "Edit Student" : "Add Student";
  if (submitEl) submitEl.textContent = mode === "edit" ? "Save Changes" : "Submit";
}

function fillStudentForm(student) {
  const form = document.getElementById("add-student-form");
  if (!form || !student) return;
  const nameInput   = form.querySelector('[name="name"]');
  const emailInput  = form.querySelector('[name="email"]');
  const statusSelect = form.querySelector('[name="status"]');
  if (nameInput)    nameInput.value    = student.name || "";
  if (emailInput)   emailInput.value   = student.sid  || "";   // sid stores email
  if (statusSelect) statusSelect.value = student.status === "Active" ? "active" : "pending";
}

async function openStudentModal(student = null) {
  setModalError("add-student-error", "");
  if (student) {
    studentModalEditingId = student.id;
    setStudentModalMode("edit");
    fillStudentForm(student);
  } else {
    studentModalEditingId = null;
    setStudentModalMode("add");
    const form = document.getElementById("add-student-form");
    if (form) form.reset();
  }
  openModal("add-student-modal");
}

async function submitStudentForm(event) {
  event.preventDefault();
  setModalError("add-student-error", "");

  const form = event.currentTarget;
  const formData = new FormData(form);
  const isEdit = studentModalEditingId != null;
  const payload = {
    name:   String(formData.get("name")  || "").trim(),
    email:  String(formData.get("email") || "").trim(),
    status: String(formData.get("status") || "active").trim(),
    gpa:    String(formData.get("gpa") || "").trim(),
  };

  try {
    const url    = isEdit ? `${STUDENTS_API_URL}${studentModalEditingId}/` : STUDENT_CREATE_API_URL;
    const method = isEdit ? "PUT" : "POST";
    const response = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json().catch(() => null);
    if (!response.ok || !data?.success) {
      throw new Error(getJsonErrorMessage(data, `Failed to save student (${response.status})`));
    }

    form.reset();
    closeModal("add-student-modal");
    showUiFeedback(data.message || (isEdit ? "Student updated." : "Student created."));
    await loadStudents();
  } catch (error) {
    setModalError("add-student-error", error.message || "Failed to save student.");
  }
}

document.addEventListener("change", (event) => {

  if (event.target.id !== "schedule-type-select") return;

  const isTask = event.target.value === "task";

  document.getElementById("task-fields").style.display =
    isTask ? "block" : "none";

  document.getElementById("defense-fields").style.display =
    isTask ? "none" : "block";

});

function editStudent(id) {
  const student = studentsState.find((s) => String(s.id) === String(id));
  if (!student) {
    showUiFeedback("Student not found. Please refresh and try again.");
    return;
  }
  openStudentModal(student);
}

function confirmDeleteStudent(id) {
  const student = studentsState.find((s) => String(s.id) === String(id));
  pendingDeleteStudentId = id;
  setModalError("delete-student-error", "");
  const nameEl = document.getElementById("delete-student-name");
  if (nameEl) nameEl.textContent = student?.name || "this student";
  openModal("delete-student-modal");
}

async function deleteStudentConfirmed() {
  if (pendingDeleteStudentId == null) return;
  setModalError("delete-student-error", "");

  try {
    const response = await fetch(`${STUDENTS_API_URL}${pendingDeleteStudentId}/`, {
      method: "DELETE",
    });
    const data = await response.json().catch(() => null);
    if (!response.ok || !data?.success) {
      throw new Error(getJsonErrorMessage(data, `Failed to delete student (${response.status})`));
    }
    closeModal("delete-student-modal");
    showUiFeedback(data.message || "Student deleted successfully.");
    pendingDeleteStudentId = null;
    await Promise.all([loadStudents(), loadTeams()]);
  } catch (error) {
    console.error("[Students] Delete failed", error);
    setModalError("delete-student-error", error.message || "Failed to delete student.");
  }
}

/* ============================================
   TEAMS SEARCH
   ============================================ */
function getTeamSupervisorLabel(team) {
  if (team?.assigned_supervisor?.display_name) {
    return String(team.assigned_supervisor.display_name);
  }
  if (!team?.supervisor_id) return "Unassigned";
  const sup = supervisorsState.find((s) => String(s?.user?.id) === String(team.supervisor_id));
  return sup ? getSupervisorFullName(sup) : `Supervisor #${team.supervisor_id}`;
}

function formatTeamStatusLabel(status) {
  const s = String(status || "").toLowerCase();
  const map = {
    forming: "Forming",
    active: "Active",
    approved: "Approved",
    rejected: "Rejected",
    completed: "Completed",
    disbanded: "Disbanded",
  };
  return map[s] || String(status || "—");
}

function normalizeTeamStatus(status) {
  const s = String(status || "").toLowerCase();
  if (s === "active" || s === "approved") return "green";
  if (s === "forming") return "amber";
  if (s === "rejected") return "red";
  return "gray";
}

function viewTeamQuick(id) {
  const team = teamsState.find((t) => String(t.id) === String(id));
  showUiFeedback(team ? `Viewing ${team.name}` : "Team");
}

function updateTeamToolbarStats() {
  const set = (id, v) => {
    const el = document.getElementById(id);
    if (el) el.textContent = String(v);
  };

  const activeTeams = teamsState.filter((team) =>
    !(team.is_archived === true || String(team.is_archived || "").toLowerCase() === "true")
  );

  const total = activeTeams.length;
  const active = activeTeams.filter(
    (t) => String(t.status).toLowerCase() === "active"
  ).length;

  const forming = activeTeams.filter(
    (t) => String(t.status).toLowerCase() === "forming"
  ).length;

  set("teams-toolbar-total", total);
  set("teams-toolbar-active", active);
  set("teams-toolbar-forming", forming);
}

async function autoCreateTeams() {

  const unassignedStudents = studentsState.filter(
    s => !s.team_id
  );

  if (unassignedStudents.length === 0) {
    showUiFeedback("No students available.");
    return;
  }

  const groups = [];

  for (let i = 0; i < unassignedStudents.length; i += 5) {
    groups.push(unassignedStudents.slice(i, i + 5));
  }

  let teamCounter = teamsState.length + 1;

  try {

    for (const group of groups) {

      const payload = {
        name: `Auto Team ${teamCounter}`,
        project_title: "GP1",
        project_description: "",
        status: "forming",
        supervisor_id: null,
        member_ids: group.map(s => s.id)
      };

      const response = await fetch(TEAMS_API_URL, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        throw new Error(`Failed to create Auto Team ${teamCounter}`);
      }

      teamCounter++;
    }

    showUiFeedback("Teams created successfully.");

    await Promise.all([
      loadTeams(),
      loadStudents(),
      loadDashboardStats()
    ]);

  } catch (error) {
    console.error(error);
    alert(error.message);
  }
}

function normalizeProposalTag(status) {
  const map = {
    approved: { cls: "blue", label: "Approved" },
    accepted: { cls: "blue", label: "Approved" },
    rejected: { cls: "red", label: "Rejected" },
    pending: { cls: "amber", label: "Pending" },
    submitted: { cls: "amber", label: "Pending" },
    under_review: { cls: "amber", label: "Pending" },
    draft: { cls: "amber", label: "Pending" },
    none: { cls: "gray", label: "None" },
  };
  return map[String(status || "").toLowerCase()] || { cls: "gray", label: String(status || "-") };
}

function renderTeams() {
  const tbody = document.getElementById("teams-table-body") || document.querySelector("#teams-table tbody");
  if (!tbody) return;

  const activeTeams = teamsState.filter((team) =>
    !(team.is_archived === true || String(team.is_archived || "").toLowerCase() === "true")
  );

  const newTeamsHTML = activeTeams.length === 0
    ? `<tr><td colspan="7" style="text-align:center;padding:32px;color:#94a3b8;">No teams found.</td></tr>`
    : activeTeams.map((team) => {
        const teamStatusClass = normalizeTeamStatus(team.status);
        const statusLabel = formatTeamStatusLabel(team.status);
        const membersCount = Number(team.members_count ?? 0);
        const st = String(team.status || "").toLowerCase();
        const isArchived = team.is_archived === true || String(team.is_archived || "").toLowerCase() === "true";
        const canReview = st === "forming";
        const approvalBtns = canReview
          ? `
            <button type="button" class="btn-approve" onclick="approveTeam(${team.id})">Activate</button>
            <button type="button" class="btn-reject" onclick="rejectTeam(${team.id})">Disband</button>
          `
          : `<span style="color:#94a3b8;font-size:12px;">—</span>`;
        const archiveBtn = st === "complete" && !isArchived
          ? `<button type="button" class="btn-secondary" onclick="archiveTeam(${team.id})">Archive</button>`
          : "";
        return `
          <tr>
            <td><strong>${escapeHtml(team.name || "-")}</strong></td>
            <td style="font-family:monospace;font-size:12px;color:#64748b">${team.id}</td>
            <td>👥 ${membersCount}</td>
            <td>${escapeHtml(team.project_title || "-")}</td>
            <td>${escapeHtml(getTeamSupervisorLabel(team))}</td>
            <td><span class="tag ${teamStatusClass}">${escapeHtml(statusLabel)}</span></td>
            <td class="actions">
              <div style="display:flex;gap:6px;flex-wrap:wrap;padding-bottom:6px">${approvalBtns}${archiveBtn}</div>
              <div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center">
                <button type="button" class="action-btn" title="View" onclick="viewTeamQuick(${team.id})">👁</button>
                <button type="button" class="action-btn" title="Edit" onclick="editTeam(${team.id})">✏️</button>
                <button type="button" class="action-btn danger" title="Delete" onclick="deleteTeam(${team.id})">🗑</button>
              </div>
            </td>
          </tr>
        `;
     }).join("");
  if (tbody.innerHTML !== newTeamsHTML) tbody.innerHTML = newTeamsHTML;
  updateTeamToolbarStats();
}

async function loadTeams() {
  try {
    const response = await fetch(TEAMS_API_URL, { method: "GET" });
    if (!response.ok) throw new Error(`Failed to load teams (${response.status})`);
    const data = await response.json();
    // API returns a flat list — normalise to the shape the rest of admin.js expects
    const raw = Array.isArray(data) ? data : [];
    teamsState = raw.map(t => ({
      ...t,
      supervisor_id: t.assigned_supervisor ? t.assigned_supervisor.id : null,
      members_count: Array.isArray(t.members) ? t.members.length : 0,
    }));
  } catch (error) {
    console.error("Error loading teams:", error);
    teamsState = [];
  } finally {
    renderTeams();
    renderArchive();
    syncStudentsTeamFilter();
    updateSupervisorStats();
    if (supervisorsState.length === 0) {
      loadSupervisors().then(() => {
        renderTeams();
      });
    }
  }
}

async function loadTeamFiles(teamId) {
  if (!teamId) return [];
  try {
    const response = await fetch(`${FILES_API_URL}?team_id=${teamId}`, { method: 'GET' });
    if (!response.ok) throw new Error(`Failed to load team files (${response.status})`);
    const data = await response.json();
    return Array.isArray(data) ? data : (data.files || data.results || []);
  } catch (error) {
    console.error("Error loading team files:", error);
    return [];
  }
}

function formatArchiveDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function renderArchive() {
  const archived = teamsState.filter((team) =>
    team.is_archived === true ||
    String(team.is_archived || "").toLowerCase() === "true"
  );

  archivedTeamsState = archived;

  const tbody = document.getElementById("archive-table-body");
  const totalEl = document.getElementById("archive-total");

  if (totalEl) {
    totalEl.textContent = archived.length;
  }

  if (!tbody) return;

  if (archived.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="6" style="text-align:center;padding:32px;color:#94a3b8;">
          No archived teams found.
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = archived.map((team) => {

    const membersCount = Array.isArray(team.members)
      ? team.members.length
      : Number(team.members_count || 0);

    const supervisor =
      team.assigned_supervisor?.display_name ||
      team.assigned_supervisor?.email ||
      getTeamSupervisorLabel(team);

    const files = Array.isArray(team.files) && team.files.length > 0
      ? team.files.map(f =>
          `<a href="${f.file_url}" download="${escapeHtml(f.file_name)}" style="display:block;color:#2563eb;text-decoration:underline;font-size:13px;margin-bottom:2px;">📄 ${escapeHtml(f.file_name)}</a>`
        ).join("")
      : `<span style="color:#94a3b8;font-size:13px;">No Files</span>`;

    return `
      <tr>
        <td><strong>${escapeHtml(team.name || "-")}</strong></td>
        <td>👥 ${membersCount}</td>
        <td>${escapeHtml(team.project_title || "-")}</td>
        <td>${escapeHtml(supervisor || "Unassigned")}</td>
        <td>${formatArchiveDate(team.archive_date)}</td>
        <td>${files}</td>
      </tr>
    `;
  }).join("");
}

async function loadArchive() {
  await loadTeams();
  const archived = teamsState.filter((team) =>
    team.is_archived === true || String(team.is_archived || "").toLowerCase() === "true"
  );
  await Promise.all(
    archived.map(async (team) => {
      team.files = await loadTeamFiles(team.id);
    })
  );
  renderArchive();
}

async function archiveTeam(id) {
  if (!id) return;
  try {
    const response = await fetch(`${TEAMS_API_URL}${id}/archive/`, { method: 'POST' });
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      const message = (data && data.error) ? data.error : `Failed to archive team (${response.status})`;
      throw new Error(message);
    }
    showUiFeedback(data?.message || "Team archived successfully.");
  } catch (error) {
    console.error("Error archiving team:", error);
    showUiFeedback(error.message || "Failed to archive team.");
  } finally {
    await loadArchive();
  }
}

async function deleteTeam(id) {
  console.log("[Teams] Delete button clicked", { id });
  const ok = confirm("Delete this team? This action cannot be undone.");
  console.log("[Teams] Delete confirm result", { id, ok });
  if (!ok) return;

  const url = `${TEAMS_API_URL}${id}/`;
  console.log("[Teams] Sending DELETE request", { id, url });
  try {
    const response = await fetch(url, { method: "DELETE" });
    let data = null;
    try {
      data = await response.json();
    } catch {
      data = null;
    }
    console.log("[Teams] Received DELETE response", { id, status: response.status, ok: response.ok, data });
    if (!response.ok || (data && data.success === false)) {
      const message = (data && data.message) ? data.message : `Failed to delete team (${response.status})`;
      throw new Error(message);
    }
    showUiFeedback((data && data.message) || "Team deleted successfully.");
  } catch (error) {
    console.error("[Teams] Delete team failed", { id, error });
    showUiFeedback(error.message || "Failed to delete team.");
  } finally {
    await Promise.all([loadTeams(), loadSupervisors(), loadDashboardStats()]);
  }
}

function fillTeamEditForm(team) {
  const form = document.getElementById("edit-team-form");
  if (!form || !team) return;

  const nameInput = form.querySelector('[name="name"]');
  const projectInput = form.querySelector('[name="project_title"]');
  const supervisorSelect = form.querySelector('[name="supervisor_id"]');
  const statusSelect = form.querySelector('[name="status"]');
  const proposalSelect = form.querySelector('[name="proposal_status"]');

  if (nameInput) nameInput.value = String(team.name || "");
  if (projectInput) projectInput.value = String(team.project_title || "");
  if (supervisorSelect) {
    const sid = team.supervisor_id != null ? String(team.supervisor_id) : "";
    supervisorSelect.value = sid;
    const hasOption = Array.from(supervisorSelect.options).some((o) => o.value === sid);
    if (sid && !hasOption) {
      supervisorSelect.insertAdjacentHTML(
        "beforeend",
        `<option value="${sid}">${escapeHtml(`Supervisor #${sid}`)}</option>`
      );
      supervisorSelect.value = sid;
    }
  }
  if (statusSelect && team.status) statusSelect.value = String(team.status);
  if (proposalSelect && team.proposal_status != null) proposalSelect.value = String(team.proposal_status);
}

async function openEditTeamModal(team) {
  setModalError("edit-team-error", "");
  teamModalEditingId = team.id;

  if (!Array.isArray(supervisorsState) || supervisorsState.length === 0) {
    await loadSupervisors();
  }
  if (!Array.isArray(studentsState) || studentsState.length === 0) {
    await loadStudents();
  }

  const supervisorSelect = document.getElementById("edit-team-supervisor-select");
  if (supervisorSelect) {
    const currentSupervisorId = team.supervisor_id != null ? String(team.supervisor_id) : "";
    const options = supervisorsState.map((s) => {
      return supervisorOptionHtml(s, currentSupervisorId);
    });
    supervisorSelect.innerHTML = [`<option value="">Unassigned</option>`, ...options.filter(Boolean)].join("");
  }

  const memberIds = Array.isArray(team.members) ? team.members.map((m) => m.id) : [];
  renderTeamMembersList('edit-team-members-list', memberIds);
  fillTeamEditForm(team);
  openModal("edit-team-modal");
}

async function editTeam(id) {
  const team = teamsState.find((t) => String(t.id) === String(id));
  if (!team) {
    showUiFeedback("Team not found in current list. Please refresh and try again.");
    return;
  }
  await openEditTeamModal(team);
}

async function submitEditTeamForm(event) {
  event.preventDefault();
  setModalError("edit-team-error", "");
  if (teamModalEditingId == null) return;

  const form = event.currentTarget;
  const formData = new FormData(form);
  const supervisorRaw = String(formData.get("supervisor_id") || "").trim();
  const selectedMemberIds = getSelectedTeamMemberIds("edit-team-members-list");

  if (selectedMemberIds.length > TEAM_MAX_MEMBERS) {
    setTeamMembersError("edit-team-members-error", `Maximum team size is ${TEAM_MAX_MEMBERS} students.`);
    return;
  }

  const payload = {
    name: String(formData.get("name") || "").trim(),
    project_title: String(formData.get("project_title") || "").trim(),
    supervisor_id: supervisorRaw ? Number(supervisorRaw) : null,
    status: String(formData.get("status") || "").trim(),
    proposal_status: String(formData.get("proposal_status") || "").trim(),
    member_ids: selectedMemberIds,
  };

  const url = `${TEAMS_API_URL}${teamModalEditingId}/`;

  try {
    const response = await fetch(url, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      throw new Error(getJsonErrorMessage(data, `Failed to update team (${response.status})`));
    }
    form.reset();
    closeModal("edit-team-modal");
    teamModalEditingId = null;
    showUiFeedback(data.message || "Team updated successfully.");
    await Promise.all([loadTeams(), loadSupervisors(), loadDashboardStats()]);
  } catch (error) {
    console.error("[Teams] Edit team failed", { id: teamModalEditingId, error });
    setModalError("edit-team-error", error.message || "Failed to update team.");
  }
}

async function approveTeam(id) {
  try {
    const response = await fetch(`${TEAMS_API_URL}${id}/approve/`, { method: "POST" });
    const data = await response.json().catch(() => null);
    if (!response.ok || !data?.success) {
      throw new Error(getJsonErrorMessage(data, `Failed to approve team (${response.status})`));
    }
    showUiFeedback(data.message || "Team approved successfully.");
    await Promise.all([loadTeams(), loadSupervisors(), loadDashboardStats()]);
  } catch (error) {
    console.error("[Teams] Approve failed", error);
    showUiFeedback(error.message || "Failed to approve team.");
  }
}

async function rejectTeam(id) {
  try {
    const response = await fetch(`${TEAMS_API_URL}${id}/reject/`, { method: "POST" });
    const data = await response.json().catch(() => null);
    if (!response.ok || !data?.success) {
      throw new Error(getJsonErrorMessage(data, `Failed to reject team (${response.status})`));
    }
    showUiFeedback(data.message || "Team rejected successfully.");
    await Promise.all([loadTeams(), loadSupervisors(), loadDashboardStats()]);
  } catch (error) {
    console.error("[Teams] Reject failed", error);
    showUiFeedback(error.message || "Failed to reject team.");
  }
}

function filterTeams() {
  const search = document.getElementById("teams-search")?.value.toLowerCase() || "";
  const rows   = document.querySelectorAll("#teams-table tbody tr");
  rows.forEach(row => {
    row.style.display = row.textContent.toLowerCase().includes(search) ? "" : "none";
  });
}

/* ============================================
   DEFENSE SCHEDULE
   ============================================ */
function renderDefense() {
  const list = document.getElementById("defense-list");
  if (!list) return;

  // Update stats cards
  const today = new Date().toISOString().slice(0, 10);
  const confirmed = defenseState.filter(d => d.date >= today).length;
  const pending   = defenseState.filter(d => d.date < today).length;
  const el = id => document.getElementById(id);
  if (el('defense-confirmed'))     el('defense-confirmed').textContent     = confirmed;
  if (el('defense-pending'))       el('defense-pending').textContent       = pending;
  if (el('defense-not-scheduled')) el('defense-not-scheduled').textContent = Math.max(0, teamsState.length - defenseState.length);

  // Populate team dropdown in schedule form
  const sel = document.getElementById('defense-team-select');
  if (sel && teamsState.length) {
    const cur = sel.value;
    sel.innerHTML = '<option value="" disabled>Choose a team…</option>' +
      teamsState.map(t => `<option value="${t.id}">${escapeHtml(t.name)}</option>`).join('');
    if (cur) sel.value = cur;
  }

  if (defenseState.length === 0) {
    list.innerHTML = `<div style="text-align:center;padding:32px;color:#94a3b8">No defense sessions found.</div>`;
    return;
  }

  list.innerHTML = defenseState.map(d => {
    const teamName   = d.team_name  || `Team #${d.team_id}`;
    const room       = d.location   || "—";
    const supervisor = d.supervisor || "—";
    const ex1        = d.examiner1_name || "—";
    const ex2        = d.examiner2_name || "—";
    return `
      <div class="defense-card">
        <div class="defense-icon">📅</div>
        <div class="defense-body">
          <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:4px">
            <div class="defense-title">🎓 Defense Meeting</div>
            <span class="tag amber">Scheduled</span>
          </div>
          <div class="defense-meta">
            <span>📅 <strong>${escapeHtml(d.date)}</strong> at <strong>${escapeHtml(d.time || "—")}</strong></span>
            <span>📍 ${escapeHtml(room)}</span>
          </div>
          <div class="defense-tags">
            <span class="defense-sup">Team: ${escapeHtml(teamName)}</span>
            <span class="defense-sup">Supervisor: ${escapeHtml(supervisor)}</span>
            <span class="defense-sup">Examiner 1: ${escapeHtml(ex1)}</span>
            <span class="defense-sup">Examiner 2: ${escapeHtml(ex2)}</span>
         </div>
        </div>
        <div style="display:flex;flex-direction:column;gap:6px">
          <button class="defense-edit" onclick="openEditDefense(${d.id},'${escapeHtml(d.date)}','${escapeHtml(d.time||'')}','${escapeHtml(room)}',${d.examiner1_id||'null'},${d.examiner2_id||'null'})">✏ Edit</button>
          <button class="defense-edit" style="background:#fee2e2;color:#dc2626" onclick="deleteDefense(${d.id})">🗑 Delete</button>
        </div>
      </div>
    `;
  }).join("");
}

function openEditDefense(id, date, time, location, ex1Id, ex2Id) {
  document.getElementById('edit-defense-id').value       = id;
  document.getElementById('edit-defense-date').value     = date;
  document.getElementById('edit-defense-time').value     = (time || '').slice(0, 5);
  document.getElementById('edit-defense-location').value = location === '—' ? '' : location;
  const ex1Sel = document.getElementById('edit-examiner1-select');
  const ex2Sel = document.getElementById('edit-examiner2-select');
  if (ex1Sel) ex1Sel.value = ex1Id || '';
  if (ex2Sel) ex2Sel.value = ex2Id || '';
  setModalError('edit-defense-error', '');
  openModal('edit-defense-modal');
}

async function deleteDefense(id) {
  if (!confirm('Delete this defense session?')) return;
  try {
    const res = await fetch(`${API_BASE_URL}/api/defense/${id}/`, { method: 'DELETE' });
    const data = await res.json().catch(() => null);
    if (!res.ok || !data?.success) throw new Error(data?.message || 'Failed to delete');
    showUiFeedback(data.message || 'Defense session deleted.');
    await loadDefense();
  } catch(e) {
    showUiFeedback(e.message || 'Failed to delete defense session.');
  }
}

async function loadDefense() {
  console.log("[Defense] Loading defense schedules", { url: DEFENSE_API_URL });
  try {
    const response = await fetch(DEFENSE_API_URL, { method: "GET" });
    console.log("[Defense] Received GET response", { status: response.status, ok: response.ok });
    if (!response.ok) throw new Error(`Failed to load defense schedules (${response.status})`);
    const data = await response.json();
    console.log("[Defense] GET response JSON", data);
    defenseState = Array.isArray(data.defenses) ? data.defenses : [];
  } catch (error) {
    console.error("[Defense] Error loading defense schedules:", error);
    defenseState = [];
  } finally {
    renderDefense();
  }
}

/* ============================================
   ACTIVITY LOG
   ============================================ */
function activityFilterCategoryFromLog(log) {
  const action = String(log.action || "").toLowerCase();
  const rel = String(log.related_type || "").toLowerCase();
  if (action.includes("approve")) return "approve";
  if (action.includes("reject")) return "reject";
  if (rel === "defense" || action.includes("defense") || action.includes("schedule")) return "schedule";
  if (rel === "supervisor") return "assign";
  if (rel === "proposal" && action.includes("created")) return "upload";
  if (rel === "proposal") return "upload";
  if (rel === "student") return "team";
  if (rel === "team") return "team";
  return "team";
}

function formatActivityTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, { month: "short", day: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

async function loadActivity() {
  try {
    const response = await fetch(ACTIVITY_API_URL, { method: "GET" });
    if (!response.ok) throw new Error(`Failed to load activity (${response.status})`);
    const data = await response.json();
    const items = Array.isArray(data.activities) ? data.activities : [];
    activityState = items.map((item) => {
      const type = activityFilterCategoryFromLog(item);
      const relLabel = String(item.related_type || "general").replace(/^\w/, (c) => c.toUpperCase());
      return {
        text: String(item.description || item.action || "").trim() || String(item.action || ""),
        action: item.action,
        related_type: item.related_type,
        team: relLabel,
        user: "Admin",
        time: formatActivityTime(item.created_at),
        type,
      };
    });
  } catch (error) {
    console.error("[Activity] Load failed", error);
    activityState = [];
  } finally {
    renderActivity();
  }
}

function renderActivity() {
  const search = (document.getElementById("activity-search")?.value || "").toLowerCase();
  const list   = document.getElementById("activity-list");
  if (!list) return;

  const rows = activityState.filter(a => {
    const hay = `${a.text} ${a.team} ${a.action || ""} ${a.related_type || ""}`.toLowerCase();
    const matchSearch = hay.includes(search);
    const matchFilter = activityFilter === "All" || a.type === activityFilter;
    return matchSearch && matchFilter;
  });

  list.innerHTML = rows.length === 0
    ? `<div style="text-align:center;padding:32px;color:#94a3b8">No activity found.</div>`
    : rows.map(a => {
        const cfg = ACT_CONFIG[a.type] || ACT_CONFIG["team"];
        const typeLabel = escapeHtml(String(a.action || cfg.label));
        return `
          <div class="activity-item">
            <div class="act-icon ${ICON_BG[a.type] || ICON_BG.team}">${cfg.emoji}</div>
            <div class="act-body">
              <div class="act-text">${escapeHtml(a.text)}</div>
              <div class="act-meta">By <strong>${escapeHtml(a.user)}</strong> &nbsp;·&nbsp; Related: <strong>${escapeHtml(a.team)}</strong></div>
            </div>
            <div class="act-right">
              <div class="act-type ${cfg.cls}">${typeLabel}</div>
              <div class="act-time">${escapeHtml(a.time)}</div>
            </div>
          </div>
        `;
      }).join("");
}

function filterActivity() { renderActivity(); }

function setActivityFilter(filter, btn) {
  activityFilter = filter;
  document.querySelectorAll("#activity .filter-btn").forEach(b => b.classList.remove("active"));
  btn.classList.add("active");
  renderActivity();
}

let uiFeedbackTimer = null;

function showUiFeedback(message) {
  const el = document.getElementById("ui-feedback");
  if (!el) return;
  el.textContent = message;
  el.classList.add("show");
  if (uiFeedbackTimer) clearTimeout(uiFeedbackTimer);
  uiFeedbackTimer = setTimeout(() => {
    el.classList.remove("show");
  }, 2600);
}

function openModal(modalId) {
  const modal = document.getElementById(modalId);
  if (!modal) return;
  modal.classList.add("open");
  modal.setAttribute("aria-hidden", "false");
  const errorEl = modal.querySelector(".modal-error");
  if (errorEl) {
    errorEl.textContent = "";
    errorEl.classList.remove("show");
  }
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (!modal) return;
  modal.classList.remove("open");
  modal.setAttribute("aria-hidden", "true");
  if (modalId === "edit-team-modal") teamModalEditingId = null;
}

function setModalError(errorId, message) {
  const el = document.getElementById(errorId);
  if (!el) return;
  if (message) {
    el.textContent = message;
    el.classList.add("show");
    return;
  }
  el.textContent = "";
  el.classList.remove("show");
}

function getJsonErrorMessage(data, fallback) {
  if (data && typeof data.message === "string" && data.message.trim()) return data.message;
  if (data && typeof data.error === "string" && data.error.trim()) return data.error;
  if (data && typeof data.detail === "string" && data.detail.trim()) return data.detail;
  return fallback;
}

async function submitAddTeamForm(event) {
  event.preventDefault();
  setModalError("add-team-error", "");

  const form     = event.currentTarget;
  const formData = new FormData(form);
  const supRaw   = formData.get("supervisor_id");
  const selectedMemberIds = getSelectedTeamMemberIds("add-team-members-list");

  if (selectedMemberIds.length > TEAM_MAX_MEMBERS) {
    setTeamMembersError("add-team-members-error", `Maximum team size is ${TEAM_MAX_MEMBERS} students.`);
    return;
  }

  const payload  = {
    name:                formData.get("name"),
    project_title:       formData.get("project_title") || formData.get("name"),
    project_description: formData.get("project_description") || "",
    status:              formData.get("status") || "forming",
    supervisor_id:       supRaw ? parseInt(supRaw) : null,
    member_ids:          selectedMemberIds,
  };

  try {
    const response = await fetch(TEAMS_API_URL, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify(payload),
    });
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      throw new Error(getJsonErrorMessage(data, `Failed to create team (${response.status})`));
    }
    closeModal("add-team-modal");
    form.reset();
    showUiFeedback("Team created successfully.");
    await Promise.all([loadTeams(), loadSupervisors(), loadDashboardStats()]);
  } catch (error) {
    setModalError("add-team-error", error.message);
  }
}

async function submitAddStudentForm(event) {
  event.preventDefault();
  setModalError("add-student-error", "");

  const form = event.currentTarget;
  const formData = new FormData(form);
  const payload = {
  name: formData.get("name"),
  email: formData.get("email"),
  gpa: formData.get("gpa"),
  };

  try {
    const token = localStorage.getItem('access');
    const response = await fetch(STUDENTS_API_URL, {
    method: "POST",
    headers: { 
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`
    },
    body: JSON.stringify(payload),
    });
    const data = await response.json().catch(() => null);
    if (!response.ok || !data?.success) {
      throw new Error(getJsonErrorMessage(data, `Failed to create student (${response.status})`));
    }
    closeModal("add-student-modal");
    form.reset();
    showUiFeedback(data.message || "Student created successfully.");
    await Promise.all([loadStudents(), loadDashboardStats()]);
  } catch (error) {
    console.error("Error creating student:", error);
    setModalError("add-student-error", error.message);
  }
}

async function submitAddProposalForm(event) {
  event.preventDefault();
  setModalError("add-proposal-error", "");

  const form = event.currentTarget;
  const formData = new FormData(form);
  const payload = {
    title: formData.get("title"),
    description: formData.get("description"),
    team_id: parseInt(formData.get("team_id")),
  };

  try {
    const response = await fetch(PROPOSALS_API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json().catch(() => null);
    if (!response.ok || !data?.success) {
      throw new Error(getJsonErrorMessage(data, `Failed to create proposal (${response.status})`));
    }
    closeModal("add-proposal-modal");
    form.reset();
    showUiFeedback(data.message || "Proposal created successfully.");
    await Promise.all([loadProposals(), loadDashboardStats()]);
  } catch (error) {
    console.error("Error creating proposal:", error);
    setModalError("add-proposal-error", error.message);
  }
}

async function submitAddSupervisorForm(event) {
  event.preventDefault();
  setModalError("add-supervisor-error", "");
  console.log("[Supervisors] Add Supervisor button clicked");

  const form = event.currentTarget;
  const formData = new FormData(form);
  const payload = {
    first_name: String(formData.get("first_name") || "").trim(),
    last_name: String(formData.get("last_name") || "").trim(),
    email: String(formData.get("email") || "").trim(),
    department: String(formData.get("department") || "").trim(),
    capacity: Number(formData.get("capacity") || 0),
  };
  console.log("[Supervisors] Sending create request", payload);

  try {
    const isEdit = supervisorModalEditingId != null;
    const url = isEdit ? `${SUPERVISORS_API_URL}${supervisorModalEditingId}/` : SUPERVISOR_CREATE_API_URL;
    const response = await fetch(url, {
      method: isEdit ? "PUT" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    console.log("[Supervisors] Received response", { status: response.status, ok: response.ok, data });
    if (!response.ok || !data.success) {
      throw new Error(getJsonErrorMessage(data, `Failed to create supervisor (${response.status})`));
    }

    form.reset();
    closeModal("add-supervisor-modal");
    supervisorModalEditingId = null;
    setSupervisorModalMode("add");
    showUiFeedback(data.message || (isEdit ? "Supervisor updated successfully." : "Supervisor created successfully."));
    await Promise.all([loadSupervisors(), loadTeams(), loadStudents(), loadProposals(), loadDashboardStats()]);
  } catch (error) {
    console.error("[Supervisors] Add supervisor failed", error);
    setModalError("add-supervisor-error", error.message || "Failed to save supervisor.");
  }
}

async function submitScheduleDefenseForm(event) {
  event.preventDefault();
  setModalError("schedule-defense-error", "");
  console.log("[Defense] Schedule Defense button clicked");

  const form = event.currentTarget;
  const formData = new FormData(form);
  const ex1Val = formData.get("examiner1_id");
  const ex2Val = formData.get("examiner2_id");
  const payload = {
    schedule_type:    String(formData.get("schedule_type") || "defense"),
    team_id:          Number(formData.get("team_id")),
    date:             String(formData.get("date") || "").trim(),
    time:             String(formData.get("time") || "").trim(),
    location:         String(formData.get("location") || "").trim(),
    examiner1_id:     ex1Val ? Number(ex1Val) : null,
    examiner2_id:     ex2Val ? Number(ex2Val) : null,
    task_title:       String(formData.get("task_title") || "").trim(),
    task_description: String(formData.get("task_description") || "").trim(),
    task_deadline:    String(formData.get("task_deadline") || "").trim(),
  };
  console.log("[Defense] Sending create request", payload);

  try {
    console.log("[Defense] Request URL", { url: DEFENSE_API_URL });
    const response = await fetch(DEFENSE_API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    console.log("[Defense] Received response", { status: response.status, ok: response.ok, data });
    if (!response.ok || !data.success) {
      throw new Error(getJsonErrorMessage(data, `Failed to schedule defense (${response.status})`));
    }

    const defense = data.data || {};

    form.reset();
    closeModal("schedule-defense-modal");
    showUiFeedback(data.message || "Defense scheduled successfully.");
    console.log("[Defense] Schedule saved successfully", { defense });
    await loadDefense();
    await Promise.all([loadTeams(), loadStudents(), loadProposals()]);
  } catch (error) {
    console.error("[Defense] Schedule defense failed", error);
    setModalError("schedule-defense-error", error.message || "Failed to schedule defense.");
  }
}

function bindModalCloseButtons() {
  document.querySelectorAll("[data-modal-close]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const modalId = btn.getAttribute("data-modal-close");
      closeModal(modalId);
    });
  });

  document.querySelectorAll(".modal-overlay").forEach((overlay) => {
    overlay.addEventListener("click", (event) => {
      if (event.target === overlay) {
        closeModal(overlay.id);
      }
    });
  });

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    document.querySelectorAll(".modal-overlay.open").forEach((modal) => {
      closeModal(modal.id);
    });
  });
}

function bindHeaderActionButtons() {
  const teamBtn = document.getElementById("btn-open-add-team");
  const supervisorBtn = document.getElementById("btn-open-add-supervisor");
  const proposalBtn = document.getElementById("btn-open-add-proposal");
  const defenseBtn = document.getElementById("btn-open-schedule-defense");
  const studentBtn = document.getElementById("btn-open-add-student");
  const teamForm = document.getElementById("add-team-form");
  const editTeamForm = document.getElementById("edit-team-form");
  const supervisorForm = document.getElementById("add-supervisor-form");
  const proposalForm = document.getElementById("add-proposal-form");
  const defenseForm = document.getElementById("schedule-defense-form");
  const studentForm = document.getElementById("add-student-form");
  const gradeForm = document.getElementById("add-grade-form");
  const confirmDeleteStudentBtn = document.getElementById("btn-confirm-delete-student");
  const confirmDeleteSupervisorBtn = document.getElementById("btn-confirm-delete-supervisor");
  const confirmDeleteProposalBtn = document.getElementById("btn-confirm-delete-proposal");
  const confirmDeleteGradeBtn = document.getElementById("btn-confirm-delete-grade");

  if (teamBtn) teamBtn.addEventListener("click", async () => {
    if (!Array.isArray(supervisorsState) || supervisorsState.length === 0) {
      await loadSupervisors();
    }
    if (!Array.isArray(studentsState) || studentsState.length === 0) {
      await loadStudents();
    }

    const sel = document.getElementById('add-team-supervisor-select');
    if (sel && supervisorsState.length) {
      sel.innerHTML = '<option value="">— None —</option>' +
        supervisorsState.map(s => supervisorOptionHtml(s)).join('');
    }
    renderTeamMembersList('add-team-members-list', []);
    openModal("add-team-modal");
  });
  if (supervisorBtn) supervisorBtn.addEventListener("click", () => openSupervisorModal());
  if (proposalBtn) proposalBtn.addEventListener("click", () => openProposalModal());
  if (defenseBtn) defenseBtn.addEventListener("click", () => {
    // Populate team dropdown before opening modal
    const sel = document.getElementById('defense-team-select');
    if (sel && teamsState.length) {
      sel.innerHTML = '<option value="" disabled selected>Choose a team…</option>' +
        teamsState.map(t => `<option value="${t.id}">${escapeHtml(t.name)}</option>`).join('');
    }
    openModal("schedule-defense-modal");
  });
  if (studentBtn) studentBtn.addEventListener("click", openStudentModal);

  if (teamForm) teamForm.addEventListener("submit", submitAddTeamForm);
  if (editTeamForm) editTeamForm.addEventListener("submit", submitEditTeamForm);
  if (supervisorForm) supervisorForm.addEventListener("submit", submitAddSupervisorForm);
  if (proposalForm) proposalForm.addEventListener("submit", submitProposalForm);
  if (defenseForm) defenseForm.addEventListener("submit", submitScheduleDefenseForm);

  const editDefenseForm = document.getElementById("edit-defense-form");
  if (editDefenseForm) editDefenseForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    setModalError('edit-defense-error', '');
    const id       = document.getElementById('edit-defense-id').value;
    const date     = document.getElementById('edit-defense-date').value;
    const time     = document.getElementById('edit-defense-time').value;
    const location = document.getElementById('edit-defense-location').value.trim() || 'TBD';
    const ex1Val   = document.getElementById('edit-examiner1-select')?.value;
    const ex2Val   = document.getElementById('edit-examiner2-select')?.value;
    try {
      const res  = await fetch(`${API_BASE_URL}/api/defense/${id}/`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          date, time, location,
          examiner1_id: ex1Val ? Number(ex1Val) : null,
          examiner2_id: ex2Val ? Number(ex2Val) : null,
        }),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok || !data?.success) throw new Error(data?.message || `Failed (${res.status})`);
      closeModal('edit-defense-modal');
      showUiFeedback(data.message || 'Defense session updated.');
      await loadDefense();
    } catch(e) {
      setModalError('edit-defense-error', e.message);
    }
  });
  if (studentForm) studentForm.addEventListener("submit", submitStudentForm);
  if (gradeForm) gradeForm.addEventListener("submit", submitGradeForm);
  if (confirmDeleteStudentBtn) confirmDeleteStudentBtn.addEventListener("click", deleteStudentConfirmed);
  if (confirmDeleteSupervisorBtn) confirmDeleteSupervisorBtn.addEventListener("click", deleteSupervisorConfirmed);
  if (confirmDeleteProposalBtn) confirmDeleteProposalBtn.addEventListener("click", deleteProposalConfirmed);
  if (confirmDeleteGradeBtn) confirmDeleteGradeBtn.addEventListener("click", deleteGradeConfirmed);

  bindModalCloseButtons();
}

/* ============================================
   GRADES
   ============================================ */
function renderGrades() {
  const search = (document.getElementById("grades-search")?.value || "").toLowerCase();
  const tbody = document.getElementById("grades-tbody");
  if (!tbody) return;

  // Use gradesState directly since it now contains all teams with grade data
  const rows = gradesState.filter(g => {
    const teamName = String(g.team_name || "").toLowerCase();
    const projectTitle = String(g.project_title || "").toLowerCase();
    const supervisorName = String(g.supervisor_name || "").toLowerCase();
    const statusLabel = normalizeGradeStatus(g.status);
    const matchSearch = teamName.includes(search) || projectTitle.includes(search) || supervisorName.includes(search);
    const matchFilter = gradeFilter === "All" || statusLabel === gradeFilter;
    return matchSearch && matchFilter;
  });

  const newGradesHTML = rows.length === 0
    ? `<tr><td colspan="10" style="text-align:center;padding:32px;color:#94a3b8;">No grades found.</td></tr>`
    : rows.map(g => {
        const statusLabel = normalizeGradeStatus(g.status);
        const statusTag = {
          Approved:   `<span class="tag green">Approved</span>`,
          Submitted:  `<span class="tag amber">Submitted</span>`,
          Incomplete: `<span class="tag orange">Incomplete</span>`,
          Draft:      `<span class="tag gray">Draft</span>`,
          Rejected:   `<span class="tag red">Rejected</span>`,
        }[statusLabel] || `<span class="tag gray">${g.status || "Unknown"}</span>`;

        const actionBtns = g.id && (statusLabel === "Draft" || statusLabel === "Submitted")
          ? `
            <button class="btn-approve" onclick="approveGrade(${g.id})">Approve</button>
            <button class="btn-reject" onclick="rejectGrade(${g.id})">Reject</button>
          `
          : `<span style="color:#94a3b8;font-size:12px;">No actions</span>`;

        const supervisorGradeDisplay = g.supervisor_grade != null 
          ? `${g.supervisor_grade.toFixed(2)} / 100` 
          : '—';
        const committee1GradeDisplay = g.committee1_grade != null 
          ? `${g.committee1_grade.toFixed(2)} / 100` 
          : '—';
        const committee2GradeDisplay = g.committee2_grade != null 
          ? `${g.committee2_grade.toFixed(2)} / 100` 
          : '—';
        const finalGradeDisplay = g.final_grade != null 
          ? `<strong class="grade-${getGradeClass(g.final_grade)}">${g.final_grade.toFixed(2)}</strong>` 
          : '—';
        const letterGradeDisplay = g.letter_grade 
          ? `<span class="tag ${getLetterGradeClass(g.letter_grade)}">${g.letter_grade}</span>` 
          : '<span class="tag gray">-</span>';

        return `
          <tr>
            <td><strong>${escapeHtml(g.team_name || "-")}</strong></td>
            <td>${escapeHtml(g.project_title || "-")}</td>
            <td>${escapeHtml(g.supervisor_name || "-")}</td>
            <td>${supervisorGradeDisplay}</td>
            <td>${committee1GradeDisplay}</td>
            <td>${committee2GradeDisplay}</td>
            <td>${finalGradeDisplay}</td>
            <td>${letterGradeDisplay}</td>
            <td>${statusTag}</td>
            <td>
              <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:6px">${actionBtns}</div>
              <div class="actions">
                <button class="action-btn" title="Edit Grade" onclick="editGrade(${g.team_id})">✏️</button>
              </div>
            </td>
          </tr>
        `;
      }).join("");

  if (tbody.innerHTML !== newGradesHTML) tbody.innerHTML = newGradesHTML;
  updateGradeCounts();
}

function normalizeGradeStatus(status) {
  const statusMap = {
    approved:   "Approved",
    submitted:  "Submitted",
    pending:    "Incomplete",
    draft:      "Draft",
    rejected:   "Rejected",
  };
  return statusMap[String(status || "").toLowerCase()] || "Draft";
}

function getGradeClass(grade) {
  if (grade >= 80) return "grade-a";
  if (grade >= 70) return "grade-b";
  if (grade >= 60) return "grade-c";
  if (grade >= 50) return "grade-d";
  return "grade-f";
}

function getLetterGradeClass(letter) {
  switch(letter) {
    case 'A+': return "green";
    case 'A': return "green";
    case 'A-': return "green";
    case 'B+': return "blue";
    case 'B': return "blue";
    case 'B-': return "blue";
    case 'C+': return "amber";
    case 'C': return "amber";
    case 'C-': return "amber";
    case 'D+': return "orange";
    case 'D': return "orange";
    case 'F': return "red";
    default: return "gray";
  }
}

function validateGradeInput(input) {
  const value = parseFloat(input.value);
  const max = parseFloat(input.max);
  const min = parseFloat(input.min);
  
  if (isNaN(value) || value < min || value > max) {
    input.style.borderColor = '#ef4444';
    return false;
  }
  
  input.style.borderColor = '#d1d5db';
  updateGradePreview();
  return true;
}

function updateGradePreview() {
  const supervisorGrade = parseFloat(document.getElementById("grade-supervisor-grade")?.value);
  const committee1Grade = parseFloat(document.getElementById("grade-committee1-grade")?.value);
  const committee2Grade = parseFloat(document.getElementById("grade-committee2-grade")?.value);
  const previewDiv = document.getElementById("grade-preview");
  
  if (!isNaN(supervisorGrade) && !isNaN(committee1Grade) && !isNaN(committee2Grade)) {
    const finalGrade = (supervisorGrade * 0.5) + (committee1Grade * 0.25) + (committee2Grade * 0.25);
    let letterGrade = '';
    if (finalGrade >= 95) letterGrade = 'A+';
    else if (finalGrade >= 85) letterGrade = 'A';
    else if (finalGrade >= 80) letterGrade = 'A-';
    else if (finalGrade >= 77) letterGrade = 'B+';
    else if (finalGrade >= 73) letterGrade = 'B';
    else if (finalGrade >= 70) letterGrade = 'B-';
    else if (finalGrade >= 67) letterGrade = 'C+';
    else if (finalGrade >= 63) letterGrade = 'C';
    else if (finalGrade >= 60) letterGrade = 'C-';
    else if (finalGrade >= 57) letterGrade = 'D+';
    else if (finalGrade >= 50) letterGrade = 'D';
    else letterGrade = 'F';
    
    document.getElementById("preview-final-grade").textContent = finalGrade.toFixed(2);
    document.getElementById("preview-letter-grade").textContent = letterGrade;
    document.getElementById("preview-letter-grade").className = `tag ${getLetterGradeClass(letterGrade)}`;
    previewDiv.style.display = 'block';
  } else {
    previewDiv.style.display = 'none';
  }
}

async function loadGrades() {
  try {
    const response = await fetch(GRADES_API_URL, { method: "GET" });
    if (!response.ok) throw new Error(`Failed to load grades (${response.status})`);

    const data = await response.json();
    gradesState = Array.isArray(data.grades) ? data.grades : (Array.isArray(data) ? data : []);
  } catch (error) {
    console.error("Error loading grades:", error);
    gradesState = [];
  } finally {
    renderGrades();
  }
}

function setGradeModalMode(mode) {
  const titleEl = document.getElementById("grade-modal-title");
  const submitEl = document.getElementById("grade-modal-submit-btn");
  if (titleEl) titleEl.textContent = mode === "edit" ? "Edit Grade" : "Add Grade";
  if (submitEl) submitEl.textContent = mode === "edit" ? "Save Changes" : "Add Grade";
}

async function openGradeModal(grade = null) {
  setModalError("add-grade-error", "");

  const loads = [];
  if (!Array.isArray(teamsState) || teamsState.length === 0) loads.push(loadTeams());
  if (loads.length) await Promise.all(loads);

  const teamSelect = document.getElementById("grade-team-select");
  if (teamSelect) {
    teamSelect.innerHTML = [
      `<option value="" disabled selected>Choose a team...</option>`,
      ...teamsState.map((t) => `<option value="${t.id}">${escapeHtml(String(t.name || `Team #${t.id}`))}</option>`),
    ].join("");
  }

  const form = document.getElementById("add-grade-form");
  if (form) form.reset();

  if (grade) {
    // Edit grade for specific team
    gradeModalEditingId = grade.team_id;
    setGradeModalMode("edit");
    if (teamSelect) {
      teamSelect.value = String(grade.team_id || "");
      teamSelect.disabled = true;
    }
    const supervisorGradeInput = form?.querySelector('[name="supervisor_grade"]');
    if (supervisorGradeInput) supervisorGradeInput.value = grade.supervisor_grade || "";
    const committee1GradeInput = form?.querySelector('[name="committee1_grade"]');
    if (committee1GradeInput) committee1GradeInput.value = grade.committee1_grade || "";
    const committee2GradeInput = form?.querySelector('[name="committee2_grade"]');
    if (committee2GradeInput) committee2GradeInput.value = grade.committee2_grade || "";
    const statusSelect = form?.querySelector('[name="status"]');
    if (statusSelect) statusSelect.value = grade.status || "draft";
  } else {
    // Add new grade (shouldn't be used anymore since we always have team context)
    gradeModalEditingId = null;
    setGradeModalMode("add");
    if (teamSelect) teamSelect.disabled = false;
    const statusSelect = form?.querySelector('[name="status"]');
    if (statusSelect) statusSelect.value = "draft";
  }

  openModal("add-grade-modal");
}

async function submitGradeForm(event) {
  event.preventDefault();
  setModalError("add-grade-error", "");

  const form = event.currentTarget;
  const formData = new FormData(form);
  
  // Get team_id - from form if adding, from editingId if editing
  const teamSelect = document.getElementById("grade-team-select");
  let teamId;
  if (gradeModalEditingId != null) {
    // Editing: use the editingId (which is team_id)
    teamId = gradeModalEditingId;
  } else {
    // Adding: use form value
    teamId = parseInt(formData.get("team_id"));
  }
  
  const payload = {
    team_id: teamId,
    supervisor_grade: parseFloat(formData.get("supervisor_grade")),
    committee1_grade: parseFloat(formData.get("committee1_grade")),
    committee2_grade: parseFloat(formData.get("committee2_grade")),
    status: formData.get("status"),
  };
  
  console.log("Grade payload:", payload);

  // Validation
  if (isNaN(payload.supervisor_grade) || payload.supervisor_grade < 0 || payload.supervisor_grade > 100) {
    setModalError("add-grade-error", "Supervisor grade must be between 0 and 100.");
    return;
  }
  if (isNaN(payload.committee1_grade) || payload.committee1_grade < 0 || payload.committee1_grade > 100) {
    setModalError("add-grade-error", "Committee Doctor 1 grade must be between 0 and 100.");
    return;
  }
  if (isNaN(payload.committee2_grade) || payload.committee2_grade < 0 || payload.committee2_grade > 100) {
    setModalError("add-grade-error", "Committee Doctor 2 grade must be between 0 and 100.");
    return;
  }

  const isEdit = gradeModalEditingId != null;
  const url = GRADE_CREATE_API_URL;
  const method = "POST";

  try {
    const response = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json().catch(() => null);
    if (!response.ok || !data?.success) {
      throw new Error(getJsonErrorMessage(data, `Failed to save grade (${response.status})`));
    }

    closeModal("add-grade-modal");
    form.reset();
    gradeModalEditingId = null;
    setGradeModalMode("add");
    showUiFeedback(data.message || (isEdit ? "Grade updated successfully." : "Grade created successfully."));
    await Promise.all([loadGrades(), loadDashboardStats()]);
  } catch (error) {
    console.error("[Grades] Save failed", error);
    setModalError("add-grade-error", error.message || "Failed to save grade.");
  }
}

async function approveGrade(id) {
  console.log("[Grades] Approve button clicked", { id });
  const grade = gradesState.find((g) => String(g.id) === String(id));
  if (!grade) return;
  if (grade.supervisor_grade == null || grade.committee1_grade == null || grade.committee2_grade == null) {
    showUiFeedback("Cannot approve grade with missing supervisor or committee grades.");
    return;
  }

  try {
    const response = await fetch(`${GRADES_API_URL}${id}/approve/`, {
      method: "POST",
    });
    if (!response.ok) throw new Error(`Failed to approve grade (${response.status})`);
    const data = await response.json().catch(() => null);
    if (!data?.success) {
      throw new Error(data.message || `Failed to approve grade (${response.status})`);
    }
    showUiFeedback(data.message || "Grade approved successfully.");
  } catch (error) {
    console.error("Error approving grade:", error);
    showUiFeedback(error.message || "Failed to approve grade.");
  } finally {
    await Promise.all([loadGrades(), loadDashboardStats()]);
  }
}

async function rejectGrade(id) {
  console.log("[Grades] Reject button clicked", { id });
  const grade = gradesState.find((g) => String(g.id) === String(id));
  if (!grade) return;

  try {
    const response = await fetch(`${GRADES_API_URL}${id}/reject/`, {
      method: "POST",
    });
    if (!response.ok) throw new Error(`Failed to reject grade (${response.status})`);
  } catch (error) {
    console.error("Error rejecting grade:", error);
  } finally {
    await Promise.all([loadGrades(), loadDashboardStats()]);
  }
}

function editGrade(teamId) {
  const grade = gradesState.find((g) => String(g.team_id) === String(teamId));
  if (!grade) {
    showUiFeedback("Team not found. Please refresh and try again.");
    return;
  }
  openGradeModal(grade);
}

function confirmDeleteGrade(id) {
  const grade = gradesState.find((g) => String(g.id) === String(id));
  if (!grade) return;
  pendingDeleteGradeId = id;
  setModalError("delete-grade-error", "");
  const nameEl = document.getElementById("delete-grade-team-name");
  if (nameEl) nameEl.textContent = grade.team_name || "this team";
  openModal("delete-grade-modal");
}

async function deleteGradeConfirmed() {
  if (pendingDeleteGradeId == null) return;
  setModalError("delete-grade-error", "");
  try {
    const response = await fetch(`${GRADES_API_URL}${pendingDeleteGradeId}/`, { method: "DELETE" });
    const data = await response.json().catch(() => null);
    if (!response.ok || !data?.success) {
      throw new Error(getJsonErrorMessage(data, `Failed to delete grade (${response.status})`));
    }
    closeModal("delete-grade-modal");
    pendingDeleteGradeId = null;
    showUiFeedback(data.message || "Grade deleted successfully.");
    await Promise.all([loadGrades(), loadDashboardStats()]);
  } catch (error) {
    console.error("[Grades] Delete failed", error);
    setModalError("delete-grade-error", error.message || "Failed to delete grade.");
  }
}

function setGradeFilter(filter, btn) {
  gradeFilter = filter;
  document.querySelectorAll(".filter-btn").forEach(b => {
    if (b.closest("#grades")) b.classList.remove("active");
  });
  btn.classList.add("active");
  renderGrades();
}

function updateGradeCounts() {
  const el = (id) => document.getElementById(id);
  if (el("dashboard-total-graded")) el("dashboard-total-graded").textContent = gradesState.filter(g => g.final_grade != null).length;
  if (el("dashboard-pending-grades")) el("dashboard-pending-grades").textContent = gradesState.filter(g => g.status === 'draft' || g.status === 'submitted').length;
  
  const gradedTeams = gradesState.filter(g => g.final_grade != null);
  if (gradedTeams.length > 0) {
    const average = gradedTeams.reduce((sum, g) => sum + g.final_grade, 0) / gradedTeams.length;
    const topGrade = Math.max(...gradedTeams.map(g => g.final_grade));
    if (el("dashboard-class-average")) el("dashboard-class-average").textContent = `${Number(average || 0).toFixed(1)}%`;
    if (el("dashboard-top-grade")) el("dashboard-top-grade").textContent = `${Number(topGrade || 0).toFixed(1)}%`;
  }
}

window.openEditDefense = openEditDefense;
window.deleteDefense   = deleteDefense;
window.approveProposal = approveProposal;
window.rejectProposal = rejectProposal;
window.editTeam = editTeam;
window.deleteTeam = deleteTeam;
window.archiveTeam = archiveTeam;
window.approveTeam = approveTeam;
window.rejectTeam = rejectTeam;
window.editStudent = editStudent;
window.confirmDeleteStudent = confirmDeleteStudent;
window.filterSupervisors = filterSupervisors;
window.editSupervisor = editSupervisor;
window.confirmDeleteSupervisor = confirmDeleteSupervisor;
window.viewProposalFile = viewProposalFile;
window.editProposal = editProposal;
window.confirmDeleteProposal = confirmDeleteProposal;
window.openGradeModal = openGradeModal;
window.editGrade = editGrade;
window.confirmDeleteGrade = confirmDeleteGrade;
window.approveGrade = approveGrade;
window.rejectGrade = rejectGrade;
window.validateGradeInput = validateGradeInput;
window.setGradeFilter = setGradeFilter;
window.renderGrades = renderGrades;

/* ============================================
   INIT — render dynamic sections on load
   ============================================ */
document.addEventListener("DOMContentLoaded", async () => {
  bindHeaderActionButtons();
  document.body.style.opacity = '0.5';
  await Promise.all([
    loadDashboardStats(),
    loadProposals(),
    loadTeams(),
    loadStudents(),
    loadSupervisors(),
    loadDefense(),
    loadGrades(),
    loadActivity(),
  ]);
  document.body.style.opacity = '1';
});
 
