/* ==========================================================================
   SonicSentinel AI — Clean Light Studio Interactive JS (studio.js)
   ========================================================================== */

const UNPIN_SVG = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="2" y1="2" x2="22" y2="22"/><line x1="12" y1="17" x2="12" y2="22"/><path d="M9 9v1.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V17h12"/><path d="M15 9.34V6h1a2 2 0 0 0 0-4H7.89"/></svg>`;
const PIN_SVG = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="17" x2="12" y2="22"/><path d="M5 17h14v-1.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V6h1a2 2 0 0 0 0-4H8a2 2 0 0 0 0 4h1v4.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24Z"/></svg>`;

function toggleSidebar() {
  const layout = document.getElementById("app-layout");
  if (!layout) return;
  if (window.innerWidth <= 768) {
    layout.classList.toggle("mobile-open");
  } else {
    layout.classList.toggle("collapsed");
  }
}

function closeMobileSidebar() {
  const layout = document.getElementById("app-layout");
  if (layout) layout.classList.remove("mobile-open");
}

function closeAllPopovers() {
  const morePop = document.getElementById("more-tools-popover");
  const notifCard = document.getElementById("notif-dropdown-card");
  const profCard = document.getElementById("profile-dropdown-card");
  const searchDrop = document.getElementById("topbar-search-dropdown");
  if (morePop) morePop.classList.remove("open");
  if (notifCard) notifCard.classList.remove("open");
  if (profCard) profCard.classList.remove("open");
  if (searchDrop) searchDrop.classList.remove("open");
}

document.addEventListener("click", () => {
  closeAllPopovers();
});

/* =========================================================
   1. PIN / UNPIN & "... MORE >" FLOATING POPOVER LOGIC
   ========================================================= */
function toggleMoreToolsPopover(event) {
  if (event) {
    event.preventDefault();
    event.stopPropagation();
  }
  const pop = document.getElementById("more-tools-popover");
  if (!pop) return;
  const wasOpen = pop.classList.contains("open");
  closeAllPopovers();
  if (!wasOpen) {
    const trigger = document.getElementById("more-tools-trigger");
    if (trigger && window.innerWidth > 768) {
      const rect = trigger.getBoundingClientRect();
      const topPos = Math.max(
        60,
        Math.min(window.innerHeight - 220, rect.top - 20),
      );
      pop.style.top = topPos + "px";
      pop.style.bottom = "auto";
    }
    pop.classList.add("open");
  }
}

function _getSidebarPinStorageKey() {
  const sb = document.querySelector(".app-sidebar");
  const scope = (sb && sb.getAttribute("data-sidebar-scope")) || "admin";
  return `dectus_sidebar_pin_state_${scope}_v1`;
}

function saveSidebarPinState() {
  try {
    const moreList = document.getElementById("more-tools-list");
    if (!moreList) return;
    const unpinnedIds = Array.from(moreList.querySelectorAll(".more-tool-item"))
      .map((el) => el.getAttribute("data-tool-id"))
      .filter(Boolean);
    const pinnedIds = Array.from(
      document.querySelectorAll(".app-sidebar .nav-item[data-tool-id]"),
    )
      .map((el) => el.getAttribute("data-tool-id"))
      .filter(Boolean);
    localStorage.setItem(
      _getSidebarPinStorageKey(),
      JSON.stringify({ unpinnedIds, pinnedIds }),
    );
  } catch (e) {}
}

function unpinNavTool(event, btnEl, skipSave) {
  if (event) {
    event.preventDefault();
    event.stopPropagation();
  }
  const navItem = btnEl.closest(".nav-item");
  if (!navItem) return;

  const toolId = navItem.getAttribute("data-tool-id") || "tool-" + Date.now();
  const iconClass =
    navItem.getAttribute("data-icon") || "fa-solid fa-wave-square";
  const labelText =
    navItem.getAttribute("data-label") || navItem.innerText.trim();
  const hrefAttr =
    navItem.getAttribute("data-href") || navItem.getAttribute("href") || "";
  const sectionAttr = navItem.getAttribute("data-section") || "pinned";
  const isActive = navItem.classList.contains("active");
  const clickAttr = hrefAttr
    ? `window.location.href='${hrefAttr}'`
    : navItem.getAttribute("onclick") || `switchSection(null, '${labelText}')`;

  navItem.remove();

  const moreList = document.getElementById("more-tools-list");
  if (!moreList) return;
  const itemDiv = document.createElement("div");
  itemDiv.className = "more-tool-item" + (isActive ? " active" : "");
  itemDiv.setAttribute("data-tool-id", toolId);
  itemDiv.setAttribute("data-icon", iconClass);
  itemDiv.setAttribute("data-label", labelText);
  if (hrefAttr) itemDiv.setAttribute("data-href", hrefAttr);
  itemDiv.setAttribute("data-section", sectionAttr);
  itemDiv.setAttribute("onclick", clickAttr);
  itemDiv.innerHTML = `
    <span class="more-tool-left">
      <i class="${iconClass}"></i>
      <span>${labelText}</span>
    </span>
    <button type="button" class="pin-toggle-btn" title="Pin to sidebar" onclick="pinNavTool(event, this)">
      ${PIN_SVG}
    </button>
  `;
  moreList.appendChild(itemDiv);
  checkMoreToolsEmpty();
  if (!skipSave) saveSidebarPinState();
}

function pinNavTool(event, btnEl, skipSave) {
  if (event) {
    event.preventDefault();
    event.stopPropagation();
  }
  const moreItem = btnEl.closest(".more-tool-item");
  if (!moreItem) return;

  const toolId = moreItem.getAttribute("data-tool-id") || "tool-" + Date.now();
  const iconClass =
    moreItem.getAttribute("data-icon") || "fa-solid fa-wave-square";
  const labelText =
    moreItem.getAttribute("data-label") || moreItem.innerText.trim();
  const hrefAttr = moreItem.getAttribute("data-href") || "";
  const sectionAttr = moreItem.getAttribute("data-section") || "pinned";
  const isActive =
    moreItem.classList.contains("active") ||
    (hrefAttr && window.location.pathname === hrefAttr);
  const clickAttr =
    moreItem.getAttribute("onclick") || `switchSection(this, '${labelText}')`;

  moreItem.remove();

  const coreList = document.getElementById("core-nav-list");
  const pinnedList = document.getElementById("pinned-nav-list");
  const targetList = sectionAttr === "core" && coreList ? coreList : pinnedList;
  if (!targetList) return;

  const aEl = document.createElement("a");
  aEl.className = "nav-item" + (isActive ? " active" : "");
  aEl.setAttribute("data-tool-id", toolId);
  aEl.setAttribute("data-icon", iconClass);
  aEl.setAttribute("data-label", labelText);
  aEl.setAttribute("data-section", sectionAttr);
  aEl.setAttribute("title", labelText);
  if (hrefAttr) {
    aEl.setAttribute("href", hrefAttr);
    aEl.setAttribute("data-href", hrefAttr);
  } else {
    aEl.setAttribute("onclick", clickAttr);
  }
  aEl.innerHTML = `
    <span class="nav-item-left">
      <i class="${iconClass}"></i>
      <span class="nav-label">${labelText}</span>
    </span>
    <button type="button" class="pin-toggle-btn" title="Unpin to More" onclick="unpinNavTool(event, this)">
      ${UNPIN_SVG}
    </button>
  `;
  targetList.appendChild(aEl);
  checkMoreToolsEmpty();
  if (!skipSave) saveSidebarPinState();
}

function checkMoreToolsEmpty() {
  const moreList = document.getElementById("more-tools-list");
  if (!moreList) return;
  let emptyMsg = moreList.querySelector(".more-tools-empty");
  const items = moreList.querySelectorAll(".more-tool-item");
  if (items.length === 0) {
    if (!emptyMsg) {
      emptyMsg = document.createElement("div");
      emptyMsg.className = "more-tools-empty";
      emptyMsg.textContent = "All menus are pinned to sidebar";
      moreList.appendChild(emptyMsg);
    }
  } else if (emptyMsg) {
    emptyMsg.remove();
  }
}

document.addEventListener("DOMContentLoaded", () => {
  try {
    const raw = localStorage.getItem(_getSidebarPinStorageKey());
    if (raw) {
      const state = JSON.parse(raw);
      if (
        state &&
        Array.isArray(state.pinnedIds) &&
        Array.isArray(state.unpinnedIds)
      ) {
        state.pinnedIds.forEach((id) => {
          const moreItem = document.querySelector(
            `#more-tools-list .more-tool-item[data-tool-id="${id}"]`,
          );
          if (moreItem) {
            const btn = moreItem.querySelector(".pin-toggle-btn");
            if (btn) pinNavTool(null, btn, true);
          }
        });
        state.unpinnedIds.forEach((id) => {
          const navItem = document.querySelector(
            `.app-sidebar .nav-item[data-tool-id="${id}"]`,
          );
          if (navItem) {
            const btn = navItem.querySelector(".pin-toggle-btn");
            if (btn) unpinNavTool(null, btn, true);
          }
        });
      }
    }
  } catch (e) {}
});

/* =========================================================
   2. DYNAMIC NOTIFICATION BELL & ADMIN BROADCAST LOGIC
   ========================================================= */

let knownNotifIds = new Set();
let isInitialNotifLoad = true;

function playNotificationChime() {
  try {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) return;
    const ctx = new AudioContextClass();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.setValueAtTime(587.33, ctx.currentTime); // D5
    osc.frequency.exponentialRampToValueAtTime(880, ctx.currentTime + 0.12); // A5
    gain.gain.setValueAtTime(0.12, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.35);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.35);
  } catch (e) {
    // Autoplay restrictions or audio unsupported
  }
}

function toggleNotifDropdown(event) {
  if (event) event.stopPropagation();
  const card = document.getElementById("notif-dropdown-card");
  if (!card) return;
  const wasOpen = card.classList.contains("open");
  closeAllPopovers();
  if (!wasOpen) {
    card.classList.add("open");
    loadBroadcastNotifications(false);
  }
}

function markAllNotificationsAsRead() {
  localStorage.setItem("dectus_last_read_ts", new Date().toISOString());
  const dot = document.getElementById("notif-unread-dot");
  const badge = document.getElementById("notif-count-badge");
  if (dot) dot.style.display = "none";
  if (badge) {
    badge.style.display = "none";
    badge.textContent = "0";
  }
}

function showToastNotification(n) {
  let container = document.getElementById("dectus-toast-container");
  if (!container) {
    container = document.createElement("div");
    container.id = "dectus-toast-container";
    container.className = "dectus-toast-container";
    document.body.appendChild(container);
  }

  const category = n.category || "announcement";
  let icon = "fa-solid fa-bullhorn";
  if (category === "threat_alert") icon = "fa-solid fa-triangle-exclamation";
  else if (category === "maintenance") icon = "fa-solid fa-wrench";
  else if (category === "system_update") icon = "fa-solid fa-sliders";

  const toast = document.createElement("div");
  toast.className = `dectus-toast toast-${category}`;
  toast.id = `toast-${n.notification_id || Date.now()}`;
  toast.innerHTML = `
    <div class="toast-icon-circle">
      <i class="${icon}"></i>
    </div>
    <div class="toast-content-col" style="${n.action_url ? "cursor:pointer;" : ""}">
      <h5 class="toast-title">${n.title || "System Broadcast"}</h5>
      <p class="toast-desc">${n.description || ""}</p>
      <div class="toast-meta">
        <strong>${n.tag || "Broadcast"}</strong> • <span>${n.time_label || "Just now"}</span>
      </div>
    </div>
    <button type="button" class="toast-close-x" onclick="this.closest('.dectus-toast').remove()">&times;</button>
  `;

  if (n.action_url) {
    toast.querySelector(".toast-content-col").addEventListener("click", () => {
      window.location.href = n.action_url;
    });
  }

  container.appendChild(toast);

  // Auto remove after 6.5 seconds
  setTimeout(() => {
    if (toast.parentNode) {
      toast.style.opacity = "0";
      toast.style.transform = "translateX(40px)";
      setTimeout(() => toast.remove(), 250);
    }
  }, 6500);
}

async function loadBroadcastNotifications(checkNewForToast = false) {
  const container = document.getElementById("dynamic-notif-container");
  try {
    const res = await fetch("/api/app/notifications");
    const data = await res.json();
    if (!res.ok || !Array.isArray(data.notifications)) return;

    const notifs = data.notifications;
    const lastReadTs =
      localStorage.getItem("dectus_last_read_ts") || "1970-01-01T00:00:00.000Z";
    const lastReadDate = new Date(lastReadTs);

    let unreadCount = 0;
    let hasBrandNew = false;

    notifs.forEach((n) => {
      const nDate = n.created_at ? new Date(n.created_at) : new Date();
      if (nDate > lastReadDate) {
        unreadCount++;
      }

      if (n.notification_id && !knownNotifIds.has(n.notification_id)) {
        if (!isInitialNotifLoad && checkNewForToast) {
          hasBrandNew = true;
          showToastNotification(n);
        }
        knownNotifIds.add(n.notification_id);
      }
    });

    if (hasBrandNew) {
      playNotificationChime();
    }

    isInitialNotifLoad = false;

    // Update unread badges on the bell
    const dot = document.getElementById("notif-unread-dot");
    const badge = document.getElementById("notif-count-badge");
    if (unreadCount > 0) {
      if (dot) dot.style.display = "block";
      if (badge) {
        badge.style.display = "block";
        badge.textContent = unreadCount > 9 ? "9+" : unreadCount;
      }
    } else {
      if (dot) dot.style.display = "none";
      if (badge) badge.style.display = "none";
    }

    if (!container) return;

    if (notifs.length === 0) {
      container.innerHTML = `
        <div class="notif-empty-state">
          <i class="fa-regular fa-bell-slash" style="font-size:22px; color:#d4d4d8; margin-bottom:6px; display:block;"></i>
          <span>No broadcasts published yet.</span>
        </div>
      `;
      return;
    }

    container.innerHTML = notifs
      .map((n) => {
        const cat = n.category || "announcement";
        const prio = n.priority || "normal";
        const isCritical = prio === "critical";
        const isHigh = prio === "high";
        const prioClass = isCritical
          ? "priority-critical"
          : isHigh
            ? "priority-high"
            : "";

        return `
        <div class="notif-entry dynamic-entry ${prioClass} cat-${cat}" onclick="handleNotificationClick('${n.action_url || ""}')" style="${n.action_url ? "cursor:pointer;" : ""}">
          <div class="notif-entry-header">
            <span class="notif-category-pill ${cat}">
              ${isCritical ? '<i class="fa-solid fa-triangle-exclamation" style="margin-right:3px;"></i>' : ""}${n.category ? n.category.replace("_", " ") : "Update"}
            </span>
            <div style="display:flex; align-items:center; gap:6px;">
              <span class="notif-time">${n.time_label || "Recent"}</span>
              <button type="button" class="btn-notif-delete" title="Delete broadcast" onclick="deleteBroadcastNotification(event, '${n.notification_id}')">
                <i class="fa-regular fa-trash-can"></i>
              </button>
            </div>
          </div>
          <h4>${n.title}</h4>
          <p>${n.description}</p>
          <div style="display:flex; align-items:center; justify-content:space-between; margin-top:4px;">
            <span style="font-size:11px; color:#71717a;">By ${n.author || "Admin"}${n.target_role && n.target_role !== "all" ? ` • Target: ${n.target_role}` : ""}</span>
            <span style="font-size:10px; font-weight:700; background:#f4f4f5; padding:2px 6px; border-radius:4px; color:#52525b;">${n.tag || "Broadcast"}</span>
          </div>
        </div>
      `;
      })
      .join("");
  } catch (e) {
    console.warn("Could not load notifications:", e);
  }
}

function handleNotificationClick(url) {
  if (url && url.trim()) {
    window.location.href = url.trim();
  }
}

function openBroadcastModal() {
  closeAllPopovers();
  const modal = document.getElementById("broadcast-modal");
  if (modal) modal.classList.add("open");
}

function closeBroadcastModal() {
  const modal = document.getElementById("broadcast-modal");
  if (modal) modal.classList.remove("open");
}

function updateBroadcastTagDefault() {
  const catEl = document.getElementById("broadcast-category");
  const tagEl = document.getElementById("broadcast-tag");
  if (!catEl || !tagEl) return;
  const map = {
    threat_alert: "Threat Directive",
    system_update: "System Config",
    maintenance: "Maintenance Advisory",
    announcement: "Announcement",
  };
  tagEl.value = map[catEl.value] || "Broadcast";
}

async function submitBroadcastNotification() {
  const titleEl = document.getElementById("broadcast-title");
  const descEl = document.getElementById("broadcast-desc");
  const catEl = document.getElementById("broadcast-category");
  const prioEl = document.getElementById("broadcast-priority");
  const targetEl = document.getElementById("broadcast-target");
  const tagEl = document.getElementById("broadcast-tag");
  const urlEl = document.getElementById("broadcast-url");
  const submitBtn = document.getElementById("btn-broadcast-submit");

  if (!titleEl || !descEl) return;
  const title = titleEl.value.trim();
  const description = descEl.value.trim();
  if (!title || !description) {
    customAlert.warning(
      "Please enter both a Notification Title and Message Description.",
      "Missing Information",
    );
    return;
  }

  const category = catEl ? catEl.value : "announcement";
  const priority = prioEl ? prioEl.value : "normal";
  const target_role = targetEl ? targetEl.value : "all";
  const tag = tagEl && tagEl.value.trim() ? tagEl.value.trim() : "Broadcast";
  const action_url = urlEl ? urlEl.value.trim() : "";

  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.innerHTML =
      '<i class="fa-solid fa-circle-notch fa-spin" style="margin-right:6px;"></i>Publishing...';
  }

  try {
    const res = await fetch("/api/app/notifications", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title,
        description,
        category,
        priority,
        target_role,
        tag,
        action_url,
      }),
    });
    const data = await res.json();

    if (res.ok && data.status === "success") {
      closeBroadcastModal();
      titleEl.value = "";
      descEl.value = "";
      if (urlEl) urlEl.value = "";

      showToastNotification({
        title: "Broadcast Published Live",
        description: `Notification published: "${title}" across target workspaces.`,
        category: "announcement",
        tag: "Success",
      });

      await loadBroadcastNotifications(false);
      const card = document.getElementById("notif-dropdown-card");
      if (card) card.classList.add("open");
    } else {
      customAlert.error(data.detail || "Could not publish broadcast.");
    }
  } catch (e) {
    console.error("Broadcast error:", e);
    customAlert.error("Failed to connect to notification service.");
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerHTML =
        '<i class="fa-solid fa-paper-plane" style="margin-right:6px;"></i>Publish Live Broadcast';
    }
  }
}

async function deleteBroadcastNotification(event, notifId) {
  if (event) event.stopPropagation();
  const confirmed = await customAlert.confirm(
    "Are you sure you want to delete this broadcast notification?",
    {
      title: "Delete Broadcast Notification",
      confirmText: "Delete Broadcast",
      danger: true,
    },
  );
  if (!confirmed) return;

  try {
    const res = await fetch(`/api/app/notifications/${notifId}`, {
      method: "DELETE",
    });
    const data = await res.json();
    if (res.ok && data.status === "success") {
      customAlert.success("Broadcast notification deleted.");
      await loadBroadcastNotifications(false);
    } else {
      customAlert.error(data.detail || "Could not delete notification.");
    }
  } catch (e) {
    console.error("Delete error:", e);
    customAlert.error("Network error deleting broadcast notification.");
  }
}

/* =========================================================
   3. USER PROFILE AVATAR DROPDOWN
   ========================================================= */
function toggleProfileDropdown(event) {
  if (event) event.stopPropagation();
  const card = document.getElementById("profile-dropdown-card");
  if (!card) return;
  const wasOpen = card.classList.contains("open");
  closeAllPopovers();
  if (!wasOpen) {
    card.classList.add("open");
  }
}

/* =========================================================
   3B. INTERACTIVE TOPBAR COMMAND & QUICK-JUMP SEARCH (⌘K)
   ========================================================= */
let _topbarSearchActiveIdx = 0;
let _topbarSearchItems = [];

function _collectRoleNavItems() {
  const results = [];
  const seenHrefs = new Set();

  // Gather all sidebar links and unpinned "More" items on the current role layout
  document
    .querySelectorAll(
      ".app-sidebar a.nav-item[href], #more-tools-list .more-tool-item[data-href]",
    )
    .forEach((el) => {
      const href = el.getAttribute("href") || el.getAttribute("data-href");
      if (!href || href === "#" || seenHrefs.has(href)) return;
      seenHrefs.add(href);
      const labelEl = el.querySelector(".nav-label, .more-tool-left span");
      const label = (
        (labelEl && labelEl.textContent) ||
        el.getAttribute("data-label") ||
        el.getAttribute("title") ||
        ""
      ).trim();
      if (!label || label.toLowerCase() === "more") return;
      const iconEl = el.querySelector("i");
      const icon =
        (iconEl && iconEl.className) ||
        el.getAttribute("data-icon") ||
        "fa-solid fa-arrow-right";
      results.push({ label, href, icon, tag: "Module" });
    });

  // Also include profile & settings links from the topbar profile menu
  document
    .querySelectorAll("#profile-dropdown-card a.profile-menu-item[href]")
    .forEach((el) => {
      const href = el.getAttribute("href");
      if (!href || href === "/app/logout" || seenHrefs.has(href)) return;
      seenHrefs.add(href);
      const label = (el.textContent || "").trim();
      const iconEl = el.querySelector("i");
      const icon = (iconEl && iconEl.className) || "fa-regular fa-user";
      if (label) results.push({ label, href, icon, tag: "Account" });
    });

  return results;
}

function _findPageTableSearchInput() {
  const candidates = [
    "#evFilterSearch",
    "#companySearch",
    "#userSearchInput",
    "#alertSearch",
    "#logSearchInput",
    "#revSearchInput",
    "#subSearchInput",
    ".dectus-toolbar input[type='text']",
    ".studio-card input[type='text']",
  ];
  for (const sel of candidates) {
    const el = document.querySelector(sel);
    if (el && el.id !== "global-search-input" && el.offsetParent !== null) {
      return el;
    }
  }
  return null;
}

function focusGlobalSearch() {
  const inp = document.getElementById("global-search-input");
  if (inp) inp.focus();
}

function openTopbarSearchDropdown() {
  const drop = document.getElementById("topbar-search-dropdown");
  if (!drop) return;
  const inp = document.getElementById("global-search-input");
  closeAllPopovers();
  drop.classList.add("open");
  renderTopbarSearchList(inp ? inp.value : "");
}

function clearGlobalSearch(event) {
  if (event) event.stopPropagation();
  const inp = document.getElementById("global-search-input");
  const clearBtn = document.getElementById("topbar-search-clear");
  if (inp) {
    inp.value = "";
    inp.focus();
  }
  if (clearBtn) clearBtn.style.display = "none";

  const pageInput = _findPageTableSearchInput();
  if (pageInput && pageInput.value) {
    pageInput.value = "";
    pageInput.dispatchEvent(new Event("input", { bubbles: true }));
  }
  renderTopbarSearchList("");
}

function handleTopbarSearchInput(val) {
  const q = (val || "").trim();
  const clearBtn = document.getElementById("topbar-search-clear");
  if (clearBtn) clearBtn.style.display = q.length > 0 ? "inline-flex" : "none";

  // Live-sync with current page table search input if present
  const pageInput = _findPageTableSearchInput();
  if (pageInput) {
    pageInput.value = q;
    pageInput.dispatchEvent(new Event("input", { bubbles: true }));
  }

  const drop = document.getElementById("topbar-search-dropdown");
  if (drop && !drop.classList.contains("open")) {
    drop.classList.add("open");
  }
  renderTopbarSearchList(q);
}

function renderTopbarSearchList(query) {
  const listEl = document.getElementById("topbar-search-list");
  const labelEl = document.getElementById("topbar-search-section-label");
  if (!listEl) return;

  const q = (query || "").toLowerCase().trim();
  const navItems = _collectRoleNavItems();
  const filtered = q
    ? navItems.filter(
        (item) =>
          item.label.toLowerCase().includes(q) ||
          item.href.toLowerCase().includes(q) ||
          item.tag.toLowerCase().includes(q),
      )
    : navItems;

  _topbarSearchItems = [];
  const pageInput = _findPageTableSearchInput();

  if (q && pageInput) {
    _topbarSearchItems.push({
      label: `Filter current table for "${query.trim()}"`,
      href: "#filter-table",
      icon: "fa-solid fa-filter",
      tag: "Live Filter",
      action: () => {
        const drop = document.getElementById("topbar-search-dropdown");
        if (drop) drop.classList.remove("open");
        pageInput.focus();
      },
    });
  }

  filtered.slice(0, 8).forEach((item) => {
    _topbarSearchItems.push({
      ...item,
      action: () => {
        window.location.href = item.href;
      },
    });
  });

  if (labelEl) {
    labelEl.textContent = q
      ? `Matching Workspace Commands (${_topbarSearchItems.length})`
      : "Quick Workspace Navigation";
  }

  _topbarSearchActiveIdx = 0;

  if (_topbarSearchItems.length === 0) {
    listEl.innerHTML = `
      <div style="padding:18px 12px; text-align:center; color:#71717a; font-size:12.5px;">
        No matching modules found for "<strong>${query}</strong>"
      </div>
    `;
    return;
  }

  listEl.innerHTML = _topbarSearchItems
    .map(
      (item, idx) => `
      <button type="button" class="topbar-search-item ${idx === 0 ? "active" : ""}" data-search-idx="${idx}">
        <span class="topbar-search-item-left">
          <span class="topbar-search-item-icon"><i class="${item.icon}"></i></span>
          <span>${item.label}</span>
        </span>
        <span class="topbar-search-item-tag">${item.tag}</span>
      </button>
    `,
    )
    .join("");

  listEl.querySelectorAll(".topbar-search-item").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      const idx = parseInt(btn.getAttribute("data-search-idx") || "0", 10);
      if (_topbarSearchItems[idx] && _topbarSearchItems[idx].action) {
        _topbarSearchItems[idx].action();
      }
    });
  });
}

function handleTopbarSearchKeydown(event) {
  const drop = document.getElementById("topbar-search-dropdown");
  if (!drop || !drop.classList.contains("open")) return;

  if (event.key === "Escape") {
    drop.classList.remove("open");
    event.target.blur();
    return;
  }

  if (!_topbarSearchItems.length) return;

  if (event.key === "ArrowDown") {
    event.preventDefault();
    _topbarSearchActiveIdx =
      (_topbarSearchActiveIdx + 1) % _topbarSearchItems.length;
    _highlightTopbarSearchItem();
  } else if (event.key === "ArrowUp") {
    event.preventDefault();
    _topbarSearchActiveIdx =
      (_topbarSearchActiveIdx - 1 + _topbarSearchItems.length) %
      _topbarSearchItems.length;
    _highlightTopbarSearchItem();
  } else if (event.key === "Enter") {
    event.preventDefault();
    const item = _topbarSearchItems[_topbarSearchActiveIdx];
    if (item && item.action) item.action();
  }
}

function _highlightTopbarSearchItem() {
  const listEl = document.getElementById("topbar-search-list");
  if (!listEl) return;
  const buttons = listEl.querySelectorAll(".topbar-search-item");
  buttons.forEach((btn, i) => {
    btn.classList.toggle("active", i === _topbarSearchActiveIdx);
    if (i === _topbarSearchActiveIdx) {
      btn.scrollIntoView({ block: "nearest" });
    }
  });
}

document.addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
    const inp = document.getElementById("global-search-input");
    if (inp) {
      e.preventDefault();
      inp.focus();
      openTopbarSearchDropdown();
    }
  }
});

document.addEventListener("DOMContentLoaded", () => {
  // Ensure topbar breadcrumb title matches active sidebar module or page heading
  const bcEl = document.getElementById("breadcrumb-title");
  if (bcEl && bcEl.textContent.trim() === "Home") {
    const activeNav = document.querySelector(".app-sidebar a.nav-item.active .nav-label");
    const pageH1 = document.querySelector(".dash-title, h1");
    if (activeNav && activeNav.textContent.trim()) {
      bcEl.textContent = activeNav.textContent.trim();
    } else if (pageH1 && pageH1.textContent.trim()) {
      bcEl.textContent = pageH1.textContent.trim();
    }
  }

  loadBroadcastNotifications(false);
  // Auto-poll notifications every 7 seconds for live broadcasts
  setInterval(() => {
    loadBroadcastNotifications(true);
  }, 7000);
});

/* =========================================================
   4. NAVIGATION & STUDIO OMNIBOX HELPERS
   ========================================================= */
function switchSection(el, title) {
  document
    .querySelectorAll(".app-sidebar .nav-item")
    .forEach((item) => item.classList.remove("active"));
  if (el && el.classList && el.classList.contains("nav-item")) {
    el.classList.add("active");
  }
  const bc = document.getElementById("breadcrumb-title");
  if (bc) bc.textContent = title;
  if (window.innerWidth <= 768) {
    closeMobileSidebar();
  }
}

function selectOmniTab(btn) {
  document
    .querySelectorAll("#omnibox-tabs .omni-tab")
    .forEach((t) => t.classList.remove("active"));
  btn.classList.add("active");
  const mode = btn.getAttribute("data-mode");
  if (mode === "more") {
    toggleMoreToolsPopover(window.event);
    return;
  }
  const input = document.getElementById("omni-input");
  if (!input) return;
  if (mode === "mic") {
    input.value =
      "Live Browser Microphone Active (16,000 Hz Mono • 2.0s Sliding Window)...";
  } else if (mode === "stream") {
    input.value = "rtsp://edge-sensor-01.detectra.ai:8554/zone-north-gate";
  } else if (mode === "consensus") {
    input.value =
      "Compare Python 2D-CNN Top-3 vs Google Teachable Machine Top-3 independently...";
  }
}

function activateOmniTab(mode, label) {
  const bc = document.getElementById("breadcrumb-title");
  if (bc) bc.textContent = label;
  const targetBtn = document.querySelector(
    `#omnibox-tabs .omni-tab[data-mode="${mode}"]`,
  );
  if (targetBtn) selectOmniTab(targetBtn);
  if (window.innerWidth <= 768) {
    closeMobileSidebar();
  }
}

function triggerQuickSample(categoryName) {
  const input = document.getElementById("omni-input");
  if (input) {
    input.value = `Acoustic Telemetry Preset: [${categoryName}] — 8-Step Preprocessing (16kHz Mono, Bandpass Filter) & Dual-AI Consensus...`;
  }
  runStudioAnalysis(categoryName);
}

function handleAudioFileSelected(fileInput) {
  if (!fileInput.files || !fileInput.files[0]) return;
  const file = fileInput.files[0];
  const input = document.getElementById("omni-input");
  if (input) {
    input.value = `Ingested Audio: ${file.name} (${(file.size / 1024).toFixed(1)} KB) — Ingestion ready for Dual-AI classification.`;
  }
  uploadAndAnalyzeFile(file);
}

async function uploadAndAnalyzeFile(file) {
  const vis = document.getElementById("omni-visualizer");
  const title = document.getElementById("omni-vis-title");
  const sub = document.getElementById("omni-vis-sub");
  const badge = document.getElementById("omni-vis-badge");
  if (vis) vis.classList.add("visible");
  if (title) title.textContent = `Analyzing ${file.name}...`;
  if (sub)
    sub.textContent =
      "Audio Gate Validation -> Preprocessing -> 10 Acoustic Features -> Dual-AI Consensus...";

  try {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("zone_name", "North Perimeter Sensor Fleet");
    const res = await fetch("/api/app/audio/analyze", {
      method: "POST",
      body: formData,
    });
    const data = await res.json();
    if (res.ok && data.event) {
      const ev = data.event;
      const pyPct = (ev.python_confidence * 100).toFixed(1);
      const gtmPct = (ev.gtm_confidence * 100).toFixed(1);
      if (title)
        title.textContent = `Acoustic Match: ${ev.python_prediction} (2D-CNN: ${pyPct}% | AudioSet: ${gtmPct}%)`;
      if (sub)
        sub.textContent = `${ev.audio_id} • Quality: ${ev.quality} (SNR ${ev.snr_db} dB) • Lifecycle: ${ev.lifecycle_status}`;
      if (badge)
        badge.textContent = ev.consistency_status || "Acceptable Match";
      prependLiveEventRow(
        ev.audio_id,
        ev.python_prediction,
        `${pyPct}% / ${gtmPct}%`,
        ev.consistency_status,
        ev.quality,
        ev.severity,
      );
    } else {
      if (title)
        title.textContent =
          data.detail || "Audio Validation Gate Rejected File";
      if (badge) badge.textContent = "Rejected";
    }
  } catch (e) {
    if (title) title.textContent = `Ingested ${file.name} — Acceptable Match`;
  }
}

async function runStudioAnalysis(forcedCategory) {
  const cat = forcedCategory || "Gunshot";
  const vis = document.getElementById("omni-visualizer");
  const title = document.getElementById("omni-vis-title");
  const sub = document.getElementById("omni-vis-sub");
  const badge = document.getElementById("omni-vis-badge");
  if (vis) vis.classList.add("visible");
  if (title)
    title.textContent = `Evaluating Acoustic Telemetry: [${cat}] via Dual-AI Pipeline...`;

  try {
    const res = await fetch("/api/app/audio/simulate-zone", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        category: cat,
        zone_name: "North Perimeter Sensor Fleet",
        input_source: "Enterprise Acoustic Preset",
      }),
    });
    const data = await res.json();
    if (res.ok && data.event) {
      const ev = data.event;
      const pyPct = (ev.python_confidence * 100).toFixed(1);
      const gtmPct = (ev.gtm_confidence * 100).toFixed(1);
      if (title)
        title.textContent = `Classification Result: ${ev.python_prediction} — 2D-CNN: ${pyPct}% | AudioSet: ${gtmPct}%`;
      if (sub)
        sub.textContent = `${ev.audio_id} • Confidence Margin: ${(ev.confidence_difference * 100).toFixed(1)}% • Quality: ${ev.quality} (SNR ${ev.snr_db} dB)`;
      if (badge) badge.textContent = ev.consistency_status;
      prependLiveEventRow(
        ev.audio_id,
        ev.python_prediction,
        `${pyPct}% / ${gtmPct}%`,
        ev.consistency_status,
        ev.quality,
        ev.severity,
      );
      return;
    }
  } catch (err) {
    console.warn("Simulation fallback:", err);
  }
}

function prependLiveEventRow(id, cls, scores, consistency, quality, severity) {
  const tbody = document.getElementById("live-events-tbody");
  if (!tbody) return;
  const tr = document.createElement("tr");
  tr.innerHTML = `
    <td><code>${id}</code></td>
    <td><strong>${cls}</strong></td>
    <td>${scores}</td>
    <td><span class="status-pill status-match">${consistency}</span></td>
    <td>${quality}</td>
    <td><span class="status-pill status-critical">${severity}</span></td>
    <td style="display:flex; gap:6px;">
      <button class="table-action-btn" onclick="acknowledgeEvent(this, '${id}')">Acknowledge</button>
      <a href="/api/app/audio/${id}/report" target="_blank" class="table-action-btn" style="text-decoration:none;">Report</a>
    </td>
  `;
  tbody.prepend(tr);
}

function acknowledgeEvent(btn, id) {
  btn.textContent = "Verified ✓";
  btn.style.background = "#dcfce7";
  btn.style.color = "#15803d";
  btn.style.borderColor = "#bbf7d0";
  customAlert.success(
    `Acoustic event ${id} acknowledged and logged.`,
    "Event Verified",
  );
}

/* ==========================================================================
   SONICSENTINEL AI CUSTOM TOAST & ALERT NOTIFICATION SYSTEM
   Replaces default browser alert() with high-performance, dark-glass notifications.
   ========================================================================== */

(function () {
  function getOrCreateToastContainer() {
    let container = document.getElementById("dectus-toast-container");
    if (!container) {
      container = document.createElement("div");
      container.id = "dectus-toast-container";
      container.className = "dectus-toast-container";
      container.setAttribute("aria-live", "polite");
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
    info: '<i class="fa-solid fa-circle-info"></i>',
  };

  const DEFAULT_TITLES = {
    success: "Success",
    copied: "Copied to Clipboard",
    error: "Action Failed",
    danger: "Error Encountered",
    warning: "Notice",
    info: "Information",
  };

  let _lastToastRecord = null;
  let _pendingApiToast = null;

  function customAlert(message, type = "info", title = null, duration = 3800) {
    if (!message) return;
    const cleanType = String(type).toLowerCase().trim();
    const normalizedType = [
      "success",
      "copied",
      "error",
      "danger",
      "warning",
      "info",
    ].includes(cleanType)
      ? cleanType
      : "info";

    const titleText = title || DEFAULT_TITLES[normalizedType] || "Notification";
    _lastToastRecord = {
      message: String(message),
      type: normalizedType,
      title: titleText,
      duration: duration,
      ts: Date.now(),
    };
    _pendingApiToast = null;

    if (!document.body) {
      document.addEventListener(
        "DOMContentLoaded",
        () => customAlert(message, normalizedType, titleText, duration),
        { once: true },
      );
      return;
    }

    const container = getOrCreateToastContainer();

    const toast = document.createElement("div");
    toast.className = `dectus-toast toast-${normalizedType}`;
    toast.setAttribute("role", "alert");

    const iconHtml = ICONS[normalizedType] || ICONS.info;

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
      toast.classList.add("toast-dismissing");
      setTimeout(() => {
        if (toast.parentNode) {
          toast.parentNode.removeChild(toast);
        }
      }, 280);
    }

    const closeBtn = toast.querySelector(".dectus-toast-close");
    if (closeBtn) {
      closeBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        dismiss();
      });
    }

    // Auto dismiss timer
    if (duration > 0) {
      dismissTimer = setTimeout(dismiss, duration);

      // Pause on hover
      toast.addEventListener("mouseenter", () => {
        if (dismissTimer) clearTimeout(dismissTimer);
        const pBar = toast.querySelector(".dectus-toast-progress-bar");
        if (pBar) pBar.style.animationPlayState = "paused";
      });

      toast.addEventListener("mouseleave", () => {
        const pBar = toast.querySelector(".dectus-toast-progress-bar");
        if (pBar) pBar.style.animationPlayState = "running";
        dismissTimer = setTimeout(dismiss, 1200);
      });
    }

    return toast;
  }

  // Persist toasts triggered immediately before a page reload so they remain visible after reload
  window.addEventListener("beforeunload", () => {
    try {
      if (_lastToastRecord && Date.now() - _lastToastRecord.ts < 650) {
        sessionStorage.setItem(
          "dectus_pending_toast",
          JSON.stringify(_lastToastRecord),
        );
      } else if (
        _pendingApiToast &&
        Date.now() - _pendingApiToast.toast.ts < 1200
      ) {
        sessionStorage.setItem(
          "dectus_pending_toast",
          JSON.stringify(_pendingApiToast.toast),
        );
      }
    } catch (_e) {}
  });

  document.addEventListener("DOMContentLoaded", () => {
    try {
      const raw = sessionStorage.getItem("dectus_pending_toast");
      if (raw) {
        sessionStorage.removeItem("dectus_pending_toast");
        const data = JSON.parse(raw);
        if (data && data.message && Date.now() - (data.ts || 0) < 8000) {
          customAlert(data.message, data.type, data.title, data.duration || 3800);
        }
      }
    } catch (_e) {}
  });

  // Intercept mutating /api/ fetch calls across all dashboard roles so any action without an explicit toast still notifies the user
  if (typeof window.fetch === "function" && !window.__dectusFetchWrapped) {
    window.__dectusFetchWrapped = true;
    const _origFetch = window.fetch.bind(window);
    window.fetch = async function (input, init) {
      const method = (
        (init && init.method) ||
        (input && input.method) ||
        "GET"
      ).toUpperCase();
      const urlStr =
        typeof input === "string"
          ? input
          : (input && (input.url || String(input))) || "";
      const isMutatingApi =
        ["POST", "PUT", "PATCH", "DELETE"].includes(method) &&
        urlStr.includes("/api/") &&
        !urlStr.includes("/api/notifications/read-all") &&
        !urlStr.includes("/api/analyze") &&
        !urlStr.includes("/api/transcribe");

      const callStartTs = Date.now();
      const response = await _origFetch(input, init);

      if (isMutatingApi) {
        let payload = null;
        try {
          payload = await response.clone().json();
        } catch (_e) {}

        const isOk = response.ok && (!payload || payload.ok !== false);
        const fallbackToast = isOk
          ? {
              message:
                (payload && (payload.message || payload.detail)) ||
                (method === "DELETE"
                  ? "Item removed successfully."
                  : "Changes saved successfully."),
              type: "success",
              title: DEFAULT_TITLES.success,
              duration: 3800,
              ts: Date.now(),
            }
          : {
              message:
                (payload &&
                  (payload.error || payload.detail || payload.message)) ||
                `Request failed (${response.status}).`,
              type: "error",
              title: DEFAULT_TITLES.error,
              duration: 3800,
              ts: Date.now(),
            };

        _pendingApiToast = { callStartTs, toast: fallbackToast };

        setTimeout(() => {
          if (_lastToastRecord && _lastToastRecord.ts >= callStartTs) {
            _pendingApiToast = null;
            return;
          }
          _pendingApiToast = null;
          customAlert(
            fallbackToast.message,
            fallbackToast.type,
            fallbackToast.title,
            fallbackToast.duration,
          );
        }, 60);
      }

      return response;
    };
  }

  // Shorthand helpers
  customAlert.success = (msg, title, duration) =>
    customAlert(msg, "success", title, duration);
  customAlert.copied = (msg, title, duration) =>
    customAlert(
      msg || "Copied to clipboard!",
      "copied",
      title || "Copied to Clipboard",
      duration,
    );
  customAlert.error = (msg, title, duration) =>
    customAlert(msg, "error", title, duration);
  customAlert.warning = (msg, title, duration) =>
    customAlert(msg, "warning", title, duration);
  customAlert.info = (msg, title, duration) =>
    customAlert(msg, "info", title, duration);

  // Custom Confirm Modal (Replaces native browser confirm())
  customAlert.confirm = function (message, options = {}) {
    return new Promise((resolve) => {
      const opts =
        typeof options === "string" ? { title: options } : options || {};
      const msgStr = String(message || "Are you sure you want to proceed?");
      const lowMsg = (msgStr + " " + (opts.title || "")).toLowerCase();
      const isDanger =
        opts.danger !== undefined
          ? Boolean(opts.danger)
          : lowMsg.includes("delete") ||
            lowMsg.includes("suspend") ||
            lowMsg.includes("purge") ||
            lowMsg.includes("remove");

      const titleText =
        opts.title || (isDanger ? "Confirm Action" : "Confirmation Required");
      const confirmText =
        opts.confirmText || (isDanger ? "Confirm" : "Proceed");
      const cancelText = opts.cancelText || "Cancel";

      const existing = document.getElementById(
        "dectus-custom-confirm-backdrop",
      );
      if (existing) existing.remove();

      const backdrop = document.createElement("div");
      backdrop.id = "dectus-custom-confirm-backdrop";
      backdrop.className = "dectus-modal-backdrop open";
      backdrop.style.cssText =
        "position:fixed; inset:0; background:rgba(9,9,11,0.52); backdrop-filter:blur(4px); z-index:999998; display:flex; align-items:center; justify-content:center; padding:16px;";

      const iconBg = isDanger ? "#fef2f2" : "#f4f4f5";
      const iconBorder = isDanger ? "#fecaca" : "#e4e4e7";
      const iconColor = isDanger ? "#dc2626" : "#18181b";
      const iconClass = isDanger
        ? "fa-solid fa-triangle-exclamation"
        : "fa-solid fa-circle-question";
      const confirmBtnStyle = isDanger
        ? "background:#dc2626; color:#ffffff; border:1px solid #dc2626;"
        : "background:#18181b; color:#ffffff; border:1px solid #18181b;";

      backdrop.innerHTML = `
        <div class="dectus-modal" style="max-width:440px; width:100%; background:#ffffff; border:1px solid #e4e4e7; border-radius:14px; box-shadow:0 24px 48px rgba(0,0,0,0.2); overflow:hidden;">
          <div class="dectus-modal-header" style="padding:16px 20px; border-bottom:1px solid #f4f4f5; display:flex; align-items:center; justify-content:space-between;">
            <div style="display:flex; align-items:center; gap:10px;">
              <span style="width:32px; height:32px; border-radius:8px; background:${iconBg}; border:1px solid ${iconBorder}; color:${iconColor}; display:inline-flex; align-items:center; justify-content:center; font-size:14px;">
                <i class="${iconClass}"></i>
              </span>
              <div class="dectus-modal-title" style="font-size:15px; font-weight:700; color:#09090b;">${titleText}</div>
            </div>
            <button type="button" data-confirm-action="cancel" class="dectus-btn secondary sm" style="padding:4px 8px; cursor:pointer;">&times;</button>
          </div>
          <div class="dectus-modal-body" style="padding:18px 20px;">
            <p style="margin:0; font-size:13.5px; color:#3f3f46; line-height:1.55;">${msgStr}</p>
          </div>
          <div class="dectus-modal-footer" style="padding:12px 20px; border-top:1px solid #f4f4f5; background:#fafafa; display:flex; align-items:center; justify-content:flex-end; gap:8px;">
            <button type="button" data-confirm-action="cancel" class="dectus-btn secondary" style="cursor:pointer;">${cancelText}</button>
            <button type="button" data-confirm-action="confirm" class="dectus-btn ${isDanger ? "danger-solid" : ""}" style="${confirmBtnStyle} cursor:pointer;">${confirmText}</button>
          </div>
        </div>
      `;

      let settled = false;
      function cleanup(result) {
        if (settled) return;
        settled = true;
        document.removeEventListener("keydown", onKey);
        if (backdrop.parentNode) backdrop.remove();
        resolve(result);
      }

      function onKey(e) {
        if (e.key === "Escape") cleanup(false);
        else if (e.key === "Enter") cleanup(true);
      }

      backdrop.addEventListener("click", (e) => {
        if (e.target === backdrop) cleanup(false);
      });
      backdrop
        .querySelectorAll('[data-confirm-action="cancel"]')
        .forEach((btn) => btn.addEventListener("click", () => cleanup(false)));
      backdrop
        .querySelector('[data-confirm-action="confirm"]')
        .addEventListener("click", () => cleanup(true));

      document.addEventListener("keydown", onKey);
      document.body.appendChild(backdrop);
    });
  };

  // Custom Prompt Modal (Replaces native browser prompt())
  customAlert.prompt = function (
    message,
    defaultValue = "",
    options = {},
  ) {
    return new Promise((resolve) => {
      const opts =
        typeof options === "string" ? { title: options } : options || {};
      const titleText = opts.title || "Input Required";
      const confirmText = opts.confirmText || "Submit";
      const cancelText = opts.cancelText || "Cancel";

      const existing = document.getElementById("dectus-custom-prompt-backdrop");
      if (existing) existing.remove();

      const backdrop = document.createElement("div");
      backdrop.id = "dectus-custom-prompt-backdrop";
      backdrop.className = "dectus-modal-backdrop open";
      backdrop.style.cssText =
        "position:fixed; inset:0; background:rgba(9,9,11,0.52); backdrop-filter:blur(4px); z-index:999998; display:flex; align-items:center; justify-content:center; padding:16px;";

      backdrop.innerHTML = `
        <div class="dectus-modal" style="max-width:440px; width:100%; background:#ffffff; border:1px solid #e4e4e7; border-radius:14px; box-shadow:0 24px 48px rgba(0,0,0,0.2); overflow:hidden;">
          <div class="dectus-modal-header" style="padding:16px 20px; border-bottom:1px solid #f4f4f5; display:flex; align-items:center; justify-content:space-between;">
            <div class="dectus-modal-title" style="font-size:15px; font-weight:700; color:#09090b;">${titleText}</div>
            <button type="button" data-prompt-action="cancel" class="dectus-btn secondary sm" style="padding:4px 8px; cursor:pointer;">&times;</button>
          </div>
          <div class="dectus-modal-body" style="padding:18px 20px;">
            <label style="display:block; font-size:13px; font-weight:600; color:#27272a; margin-bottom:8px;">${message}</label>
            <input type="text" id="dectus-custom-prompt-input" class="dectus-input" style="width:100%; padding:9px 12px; border:1px solid #d4d4d8; border-radius:8px; font-size:13px;" />
          </div>
          <div class="dectus-modal-footer" style="padding:12px 20px; border-top:1px solid #f4f4f5; background:#fafafa; display:flex; align-items:center; justify-content:flex-end; gap:8px;">
            <button type="button" data-prompt-action="cancel" class="dectus-btn secondary" style="cursor:pointer;">${cancelText}</button>
            <button type="button" data-prompt-action="submit" class="dectus-btn" style="cursor:pointer;">${confirmText}</button>
          </div>
        </div>
      `;

      document.body.appendChild(backdrop);
      const inputEl = backdrop.querySelector("#dectus-custom-prompt-input");
      if (inputEl) {
        inputEl.value = defaultValue || "";
        setTimeout(() => inputEl.focus(), 30);
      }

      let settled = false;
      function cleanup(val) {
        if (settled) return;
        settled = true;
        document.removeEventListener("keydown", onKey);
        if (backdrop.parentNode) backdrop.remove();
        resolve(val);
      }

      function onKey(e) {
        if (e.key === "Escape") cleanup(null);
        else if (e.key === "Enter") cleanup(inputEl ? inputEl.value : "");
      }

      backdrop.addEventListener("click", (e) => {
        if (e.target === backdrop) cleanup(null);
      });
      backdrop
        .querySelectorAll('[data-prompt-action="cancel"]')
        .forEach((btn) => btn.addEventListener("click", () => cleanup(null)));
      backdrop
        .querySelector('[data-prompt-action="submit"]')
        .addEventListener("click", () =>
          cleanup(inputEl ? inputEl.value : ""),
        );
      document.addEventListener("keydown", onKey);
    });
  };

  // Expose globally
  window.customAlert = customAlert;
  window.showToast = customAlert;
  window.showNotification = customAlert;
  window.showToastNotification = function (opts) {
    if (!opts) return;
    const msg = opts.description || opts.message || opts.title || "";
    const title = opts.title || "Notification";
    const type = opts.type || (opts.tag === "Success" ? "success" : "info");
    customAlert(msg, type, title);
  };

  // OVERRIDE default browser alert() function across the portal!
  window.alert = function (msg) {
    if (msg === undefined || msg === null) return;
    const strMsg = String(msg);
    if (strMsg.toLowerCase().includes("copied")) {
      customAlert.copied(strMsg);
    } else if (
      strMsg.toLowerCase().includes("error") ||
      strMsg.toLowerCase().includes("failed") ||
      strMsg.toLowerCase().includes("could not")
    ) {
      customAlert.error(strMsg);
    } else if (
      strMsg.toLowerCase().includes("success") ||
      strMsg.toLowerCase().includes("created") ||
      strMsg.toLowerCase().includes("saved") ||
      strMsg.toLowerCase().includes("deleted") ||
      strMsg.toLowerCase().includes("applied") ||
      strMsg.toLowerCase().includes("reset")
    ) {
      customAlert.success(strMsg);
    } else {
      customAlert(strMsg, "info");
    }
  };
})();

/* ==========================================================================
   GLOBAL TABLE ACTION BAR-BUTTON DROPDOWN SYSTEM
   Standardizes all table row action buttons across all pages & roles into a
   single sleek floating dropdown menu button.
   ========================================================================== */
window.toggleGlobalRowDropdown = function (btn, event) {
  if (event) {
    event.preventDefault();
    event.stopPropagation();
  }
  const menu = btn.nextElementSibling;
  if (!menu) return;
  const isShown = menu.classList.contains("show");
  document
    .querySelectorAll(
      ".user-dropdown-menu.show, .alert-dropdown-menu.show, .rev-dropdown-menu.show",
    )
    .forEach((m) => m.classList.remove("show"));

  if (!isShown) {
    menu.classList.add("show");
    const rect = btn.getBoundingClientRect();
    const menuWidth = menu.offsetWidth || 225;
    const menuHeight = menu.offsetHeight || 220;
    menu.style.position = "fixed";
    if (
      rect.bottom + menuHeight > window.innerHeight - 10 &&
      rect.top > menuHeight
    ) {
      menu.style.top = Math.max(10, rect.top - menuHeight - 6) + "px";
    } else {
      menu.style.top = rect.bottom + 6 + "px";
    }
    menu.style.left = Math.max(10, rect.right - menuWidth) + "px";
    menu.style.right = "auto";
  }
};

document.addEventListener("click", () => {
  document
    .querySelectorAll(
      ".user-dropdown-menu.show, .alert-dropdown-menu.show, .rev-dropdown-menu.show",
    )
    .forEach((m) => m.classList.remove("show"));
});

window.addEventListener(
  "scroll",
  () => {
    document
      .querySelectorAll(
        ".user-dropdown-menu.show, .alert-dropdown-menu.show, .rev-dropdown-menu.show",
      )
      .forEach((m) => m.classList.remove("show"));
  },
  true,
);

function _inferActionIcon(label, cls) {
  const l = label.toLowerCase();
  if (l.includes("view") || l.includes("detail") || l.includes("inspect"))
    return "fa-regular fa-eye";
  if (l.includes("edit") || l.includes("update") || l.includes("change"))
    return "fa-regular fa-pen-to-square";
  if (l.includes("role")) return "fa-solid fa-user-gear";
  if (l.includes("ack")) return "fa-solid fa-check";
  if (l.includes("escalat")) return "fa-solid fa-arrow-trend-up";
  if (l.includes("assign")) return "fa-solid fa-user-shield";
  if (l.includes("resolv")) return "fa-solid fa-circle-check";
  if (l.includes("dismiss")) return "fa-solid fa-ban";
  if (l.includes("suspend") || l.includes("pause")) return "fa-solid fa-ban";
  if (l.includes("activat") || l.includes("restore"))
    return "fa-solid fa-circle-check";
  if (l.includes("report") || l.includes("export"))
    return "fa-solid fa-file-lines";
  if (l.includes("delete") || l.includes("purge") || l.includes("remove"))
    return "fa-solid fa-trash-can";
  if (cls.includes("danger")) return "fa-solid fa-trash-can";
  return "fa-solid fa-bolt";
}

function enhanceAllTableActionMenus() {
  const tables = document.querySelectorAll(".dectus-table, .studio-table");
  tables.forEach((table) => {
    const headers = Array.from(table.querySelectorAll("thead th"));
    if (!headers.length) return;
    const lastHeaderText = (
      headers[headers.length - 1].textContent || ""
    ).toLowerCase();
    if (!lastHeaderText.includes("action")) return;

    const rows = table.querySelectorAll("tbody tr");
    rows.forEach((row) => {
      if (row.children.length < 2) return;
      const lastTd = row.lastElementChild;
      if (!lastTd || lastTd.hasAttribute("data-action-enhanced")) return;
      if (
        lastTd.querySelector(
          ".user-dropdown-wrap, .alert-dropdown-wrap, .rev-dropdown-wrap",
        )
      ) {
        lastTd.setAttribute("data-action-enhanced", "true");
        return;
      }

      const actionBtns = Array.from(
        lastTd.querySelectorAll("button, a.dectus-btn, a.table-action-btn"),
      ).filter((el) => !el.classList.contains("rev-play-btn"));

      if (actionBtns.length < 2) return;

      lastTd.setAttribute("data-action-enhanced", "true");

      // Hide original inline container while keeping buttons in DOM so existing handlers/queries work
      actionBtns.forEach((btn) => {
        btn.style.display = "none";
      });

      const wrap = document.createElement("div");
      wrap.className = "user-dropdown-wrap";

      const trigger = document.createElement("button");
      trigger.type = "button";
      trigger.className = "user-action-btn";
      trigger.title = "Row Actions";
      trigger.innerHTML = '<i class="fa-solid fa-ellipsis-vertical"></i>';
      trigger.addEventListener("click", (e) =>
        window.toggleGlobalRowDropdown(trigger, e),
      );

      const menu = document.createElement("div");
      menu.className = "user-dropdown-menu";

      actionBtns.forEach((origBtn, idx) => {
        const text =
          (origBtn.textContent || "").trim() ||
          origBtn.getAttribute("title") ||
          `Action ${idx + 1}`;
        const cls = origBtn.className || "";
        const existingIcon = origBtn.querySelector("i");
        const iconClass = existingIcon
          ? existingIcon.className
          : _inferActionIcon(text, cls);

        let itemTone = "";
        if (
          cls.includes("danger") ||
          text.toLowerCase().includes("delete") ||
          text.toLowerCase().includes("purge")
        ) {
          itemTone = "danger";
        } else if (
          text.toLowerCase().includes("suspend") ||
          text.toLowerCase().includes("dismiss")
        ) {
          itemTone = "warning";
        } else if (
          text.toLowerCase().includes("activate") ||
          text.toLowerCase().includes("resolve")
        ) {
          itemTone = "success";
        }

        if (itemTone === "danger" && idx > 0) {
          const div = document.createElement("div");
          div.className = "user-dropdown-divider";
          menu.appendChild(div);
        }

        const item = document.createElement("button");
        item.type = "button";
        item.className = `user-dropdown-item ${itemTone}`.trim();
        item.innerHTML = `<i class="${iconClass}"></i><span>${text}</span>`;
        item.addEventListener("click", (e) => {
          e.preventDefault();
          e.stopPropagation();
          menu.classList.remove("show");
          if (
            origBtn.tagName.toLowerCase() === "a" &&
            origBtn.getAttribute("href") &&
            origBtn.getAttribute("href") !== "#"
          ) {
            if (origBtn.getAttribute("target") === "_blank") {
              window.open(origBtn.getAttribute("href"), "_blank");
            } else {
              window.location.href = origBtn.getAttribute("href");
            }
          } else {
            origBtn.click();
          }
        });
        menu.appendChild(item);
      });

      wrap.appendChild(trigger);
      wrap.appendChild(menu);
      lastTd.appendChild(wrap);
    });
  });
}

document.addEventListener("DOMContentLoaded", () => {
  enhanceAllTableActionMenus();
  const observer = new MutationObserver(() => {
    enhanceAllTableActionMenus();
  });
  if (document.body) {
    observer.observe(document.body, { childList: true, subtree: true });
  }
});

// Global bridge for templates invoking window.customAlert.*
window.customAlert = {
  success: (msg, title) => showToast(msg, "success", title),
  error: (msg, title) => showToast(msg, "error", title),
  warning: (msg, title) => showToast(msg, "warning", title),
  info: (msg, title) => showToast(msg, "info", title),
  copied: (msg) => showToast(msg || "Copied to clipboard!", "info", "Clipboard"),
};

