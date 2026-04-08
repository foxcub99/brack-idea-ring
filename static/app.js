(() => {
  const state = {
    currentPage: "",
    pollTimer: null,
    lastVersion: null,
    globalInstalled: false,
    draggedTeamId: null,
    draggedLeaderId: null,
    draggedIdeaId: null,
    draggedBracketId: null,
    pendingIdeaBracketId: null,
    pendingBracketLinkSource: null,
  };

  const apiUrl = "/api/master/action";

  function $(selector, root = document) {
    return root.querySelector(selector);
  }

  function $all(selector, root = document) {
    return Array.from(root.querySelectorAll(selector));
  }

  async function api(action, payload = {}) {
    const response = await fetch(apiUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, ...payload }),
    });
    if (!response.ok) {
      throw new Error(`Request failed: ${response.status}`);
    }
    const result = await response.json();
    await refreshLiveRoot();
    return result;
  }

  async function refreshLiveRoot() {
    const root = $("#live-root[data-live-region]");
    if (!root) {
      return;
    }
    const response = await fetch(window.location.href, { cache: "no-store" });
    if (!response.ok) {
      return;
    }
    const html = await response.text();
    const nextDoc = new DOMParser().parseFromString(html, "text/html");
    const nextRoot = nextDoc.querySelector("#live-root[data-live-region]");
    if (!nextRoot) {
      return;
    }
    root.innerHTML = nextRoot.innerHTML;
    init(document.body.dataset.page || "");
  }

  async function pollState() {
    const pollUrl = document.body.dataset.statePollUrl;
    if (!pollUrl || document.body.dataset.autoRefresh !== "1") {
      return;
    }
    try {
      const response = await fetch(pollUrl, { cache: "no-store" });
      if (!response.ok) {
        return;
      }
      const data = await response.json();
      if (state.lastVersion === null) {
        state.lastVersion = data.version;
        return;
      }
      if (data.version && data.version !== state.lastVersion) {
        state.lastVersion = data.version;
        await refreshLiveRoot();
      }
    } catch (error) {
      // silent retry
    }
  }

  function startPolling() {
    if (state.pollTimer) {
      clearInterval(state.pollTimer);
      state.pollTimer = null;
    }
    if (document.body.dataset.autoRefresh !== "1") {
      return;
    }
    pollState();
    state.pollTimer = setInterval(pollState, 3000);
  }

  function getTabName() {
    return localStorage.getItem("bir-master-tab") || "game";
  }

  function setTabName(tabName) {
    localStorage.setItem("bir-master-tab", tabName);
  }

  function getStoredIdeaSort() {
    return localStorage.getItem("bir-idea-sort") || "submitted";
  }

  function getStoredIdeaDirection() {
    return localStorage.getItem("bir-idea-direction") || "desc";
  }

  function isIdeaDescriptionShown() {
    return localStorage.getItem("bir-ideas-show-description") === "1";
  }

  function isIdeasCompact() {
    return localStorage.getItem("bir-ideas-compact") === "1";
  }

  function activateTab(tabName) {
    const buttons = $all("[data-tab-button]");
    const panels = $all("[data-tab-panel]");
    buttons.forEach((button) => {
      const active = button.dataset.tabButton === tabName;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-selected", active ? "true" : "false");
    });
    panels.forEach((panel) => {
      panel.classList.toggle("is-active", panel.dataset.tabPanel === tabName);
    });
    setTabName(tabName);
  }

  function installGlobalHandlers() {
    if (state.globalInstalled) {
      return;
    }
    state.globalInstalled = true;

    document.addEventListener("click", async (event) => {
      const tabButton = event.target.closest("[data-tab-button]");
      if (tabButton) {
        activateTab(tabButton.dataset.tabButton);
        return;
      }

      const teamSave = event.target.closest("[data-team-save]");
      if (teamSave) {
        const row = teamSave.closest("[data-team-row]");
        if (!row) return;
        const payload = {
          team_id: row.dataset.teamId,
          name: $("[data-team-field='name']", row)?.value || "",
          description: $("[data-team-field='description']", row)?.value || "",
          color: $("[data-team-field='color']", row)?.value || "#2563eb",
        };
        await api("update_team", payload);
        return;
      }

      const teamCreate = event.target.closest("[data-team-create]");
      if (teamCreate) {
        const row = teamCreate.closest("[data-team-new-row]");
        if (!row) return;
        const nameInput = $("[data-team-new-name]", row);
        const descriptionInput = $("[data-team-new-description]", row);
        const colorInput = $("[data-team-new-color]", row);
        if (!nameInput.value.trim()) {
          nameInput.focus();
          return;
        }
        await api("create_team", {
          name: nameInput.value,
          description: descriptionInput?.value || "",
          color: colorInput?.value || "#2563eb",
        });
        return;
      }

      const leaderCard = event.target.closest("[data-leader-card]");
      if (leaderCard) {
        openLeaderModal(leaderCard);
        return;
      }

      const leaderClose = event.target.closest("[data-leader-close]");
      if (leaderClose) {
        closeLeaderModal();
        return;
      }

      const ideaEdit = event.target.closest("[data-idea-edit]");
      if (ideaEdit) {
        const card = ideaEdit.closest("[data-idea-card]");
        if (card) {
          openIdeaModal(card);
        }
        return;
      }

      const ideaClose = event.target.closest("[data-idea-close]");
      if (ideaClose) {
        closeIdeaModal();
        return;
      }

      const bracketEdit = event.target.closest("[data-bracket-edit]");
      if (bracketEdit) {
        const card = bracketEdit.closest("[data-bracket-card]");
        if (card) {
          selectBracketForEdit(card);
        }
        return;
      }

      const detailsToggle = event.target.closest("[data-ideas-toggle-details]");
      if (detailsToggle) {
        const panel = $("[data-ideas-panel]");
        if (!panel) return;
        panel.classList.toggle("compact-ideas");
        applyIdeaDisplayMode();
        return;
      }

      const backdropLeader = event.target.closest("[data-leader-modal]");
      if (backdropLeader && event.target === backdropLeader) {
        closeLeaderModal();
        return;
      }

      const backdropIdea = event.target.closest("[data-idea-modal]");
      if (backdropIdea && event.target === backdropIdea) {
        closeIdeaModal();
      }
    });

    document.addEventListener("submit", async (event) => {
      const form = event.target.closest("[data-api-form]");
      if (!form) return;
      event.preventDefault();
      const action = form.dataset.apiForm;
      const payload = {};
      new FormData(form).forEach((value, key) => {
        if (payload[key] === undefined) {
          payload[key] = value;
        } else if (Array.isArray(payload[key])) {
          payload[key].push(value);
        } else {
          payload[key] = [payload[key], value];
        }
      });
      if (action === "update_bracket") {
        const selected = $("[data-bracket-select]", form)?.value;
        if (selected) {
          payload.bracket_id = selected;
        }
      }
      await api(action, payload);
      if (action === "update_leader") closeLeaderModal();
      if (action === "update_idea") closeIdeaModal();
    });

    document.addEventListener("dragstart", (event) => {
      const teamRow = event.target.closest("[data-team-row]");
      const leaderCard = event.target.closest("[data-leader-card]");
      const ideaCard = event.target.closest("[data-idea-card], [data-idea-chip]");
      const bracketHandle = event.target.closest("[data-bracket-link-handle]");

      if (teamRow) {
        state.draggedTeamId = teamRow.dataset.teamId;
        event.dataTransfer?.setData("text/plain", `team:${state.draggedTeamId}`);
      } else if (leaderCard) {
        state.draggedLeaderId = leaderCard.dataset.leaderId;
        event.dataTransfer?.setData("text/plain", `leader:${state.draggedLeaderId}`);
      } else if (ideaCard) {
        state.draggedIdeaId = ideaCard.dataset.ideaId;
        event.dataTransfer?.setData("text/plain", `idea:${state.draggedIdeaId}`);
      } else if (bracketHandle) {
        state.draggedBracketId = bracketHandle.closest("[data-bracket-card]")?.dataset.bracketId || null;
        event.dataTransfer?.setData("text/plain", `bracket:${state.draggedBracketId}`);
      }
    });

    document.addEventListener("dragover", (event) => {
      if (event.target.closest("[data-team-row], [data-team-column], [data-bracket-card]")) {
        event.preventDefault();
      }
    });

    document.addEventListener("drop", async (event) => {
      const teamRow = event.target.closest("[data-team-row]");
      const teamColumn = event.target.closest("[data-team-column]");
      const bracketCard = event.target.closest("[data-bracket-card]");
      const payloadText = event.dataTransfer?.getData("text/plain") || "";

      if (teamRow && payloadText.startsWith("team:") && state.draggedTeamId) {
        event.preventDefault();
        const rows = $all("[data-team-row]").filter((row) => row.dataset.teamId !== "unassigned");
        const targetIndex = rows.indexOf(teamRow);
        const ordered = rows.map((row) => row.dataset.teamId).filter(Boolean);
        const currentIndex = ordered.indexOf(state.draggedTeamId);
        if (currentIndex >= 0 && targetIndex >= 0) {
          ordered.splice(currentIndex, 1);
          ordered.splice(targetIndex, 0, state.draggedTeamId);
          await api("reorder_teams", { team_ids: ordered });
        }
        state.draggedTeamId = null;
        return;
      }

      if (teamColumn && payloadText.startsWith("leader:") && state.draggedLeaderId) {
        event.preventDefault();
        await api("move_leader", {
          leader_id: state.draggedLeaderId,
          team_id: teamColumn.dataset.teamId,
        });
        state.draggedLeaderId = null;
        return;
      }

      if (bracketCard && payloadText.startsWith("idea:") && state.draggedIdeaId) {
        event.preventDefault();
        await api("move_idea", {
          idea_id: state.draggedIdeaId,
          bracket_id: bracketCard.dataset.bracketId,
        });
        state.draggedIdeaId = null;
        return;
      }

      if (bracketCard && payloadText.startsWith("bracket:") && state.draggedBracketId) {
        event.preventDefault();
        const source = state.draggedBracketId;
        const target = bracketCard.dataset.bracketId;
        if (source && target && source !== target) {
          await api("link_brackets", {
            source_bracket_id: source,
            target_bracket_id: target,
          });
        }
        state.draggedBracketId = null;
      }
    });

    document.addEventListener("input", async (event) => {
      const nameInput = event.target.closest("[data-team-new-name]");
      if (nameInput) {
        const row = nameInput.closest("[data-team-new-row]");
        if (!row) return;
        if (nameInput.value.trim()) {
          // let the user keep typing; submit on Enter, blur, or Create button
        }
      }
    });

    document.addEventListener("change", async (event) => {
      const nameInput = event.target.closest("[data-team-new-name]");
      if (!nameInput) return;
      const row = nameInput.closest("[data-team-new-row]");
      if (!row) return;
      if (nameInput.value.trim()) {
        const descriptionInput = $("[data-team-new-description]", row);
        const colorInput = $("[data-team-new-color]", row);
        await api("create_team", {
          name: nameInput.value,
          description: descriptionInput?.value || "",
          color: colorInput?.value || "#2563eb",
        });
      }
    });

    document.addEventListener("keydown", async (event) => {
      const nameInput = event.target.closest("[data-team-new-name]");
      if (nameInput && event.key === "Enter") {
        event.preventDefault();
        const row = nameInput.closest("[data-team-new-row]");
        if (!row) return;
        const descriptionInput = $("[data-team-new-description]", row);
        const colorInput = $("[data-team-new-color]", row);
        if (nameInput.value.trim()) {
          await api("create_team", {
            name: nameInput.value,
            description: descriptionInput?.value || "",
            color: colorInput?.value || "#2563eb",
          });
        }
      }
    });
  }

  function openLeaderModal(card) {
    const modal = $("[data-leader-modal]");
    if (!modal) return;
    $("[data-leader-id-field]", modal).value = card.dataset.leaderId || "";
    $("[data-leader-name-field]", modal).value = card.dataset.leaderName || "";
    $("[data-leader-type-field]", modal).value = card.dataset.leaderType || "";
    $("[data-leader-site-field]", modal).value = card.dataset.leaderSite || "";
    $("[data-leader-submit-field]", modal).checked = card.dataset.leaderCanSubmit === "1";
    modal.classList.remove("hidden");
  }

  function closeLeaderModal() {
    const modal = $("[data-leader-modal]");
    if (modal) modal.classList.add("hidden");
  }

  function openIdeaModal(card) {
    const modal = $("[data-idea-modal]");
    if (!modal) return;
    $("[data-idea-id-field]", modal).value = card.dataset.ideaId || "";
    $("[data-idea-title-field]", modal).value = card.dataset.ideaTitle || "";
    $("[data-idea-category-field]", modal).value = card.dataset.ideaCategory || "General";
    $("[data-idea-description-field]", modal).value = card.dataset.ideaDescription || "";
    const assignedLeaderField = $("[data-idea-assigned-leader-field]", modal);
    const assignedTeamField = $("[data-idea-assigned-team-field]", modal);
    if (assignedLeaderField) assignedLeaderField.value = card.dataset.ideaAssignedLeaderId || "";
    if (assignedTeamField) assignedTeamField.value = card.dataset.ideaAssignedTeamId || "";
    $("[data-idea-bracket-field]", modal).value = card.dataset.ideaBracketId || "";
    modal.classList.remove("hidden");
  }

  function closeIdeaModal() {
    const modal = $("[data-idea-modal]");
    if (modal) modal.classList.add("hidden");
  }

  function selectBracketForEdit(card) {
    const select = $("[data-bracket-select]");
    const hidden = $("[data-bracket-edit-id]");
    const form = select?.closest("[data-api-form='update_bracket']");
    if (select) select.value = card.dataset.bracketId || "";
    if (hidden) hidden.value = card.dataset.bracketId || "";
    if (form) {
      const nameField = $("input[name='name']", form);
      const typeField = $("select[name='bracket_type']", form);
      const targetField = $("input[name='target_count']", form);
      const descField = $("textarea[name='description']", form);
      if (nameField) nameField.value = card.dataset.bracketName || "";
      if (typeField) typeField.value = card.dataset.bracketType || "";
      if (targetField) targetField.value = card.dataset.bracketTargetCount || "";
      if (descField) descField.value = card.dataset.bracketDescription || "";
    }
  }

  function applyIdeaDisplayMode() {
    const ideasPanel = $("[data-ideas-panel]");
    const layout = $("[data-ideas-layout]");
    const compact = ideasPanel?.classList.contains("compact-ideas");
    if (layout) {
      layout.classList.toggle("compact", compact);
    }
    const ideaCards = $all("[data-idea-card]");
    ideaCards.forEach((card) => {
      card.classList.toggle("compact", compact);
    });
  }

  function updateIdeaDescriptionVisibility() {
    const list = $("[data-ideas-list]");
    const toggle = $("[data-ideas-toggle-description]");
    if (!list || !toggle) {
      return;
    }
    const showDescriptions = isIdeaDescriptionShown();
    list.classList.toggle("show-descriptions", showDescriptions);
    toggle.textContent = showDescriptions ? "Hide descriptions" : "Show descriptions";
  }

  function dismissResetAlertAfterDelay() {
    const alerts = $all(".alert");
    alerts.forEach((alert) => {
      if ((alert.textContent || "").trim() === "Game state reset to template.") {
        window.setTimeout(() => {
          alert.remove();
        }, 5000);
      }
    });
  }

  function applyIdeasSort() {
    const list = $("[data-ideas-list]");
    if (!list) return;
    const sortBy = $("[data-ideas-sort]")?.value || "submitted";
    const direction = $("[data-ideas-direction]")?.value || "desc";
    const cards = $all("[data-idea-card]", list);
    const sorted = cards.sort((a, b) => {
      const valueOf = (card, key) => (card.dataset[`idea${key}`] || card.dataset[`idea${key[0].toUpperCase()}${key.slice(1)}`] || "");
      const map = {
        submitted: (card) => card.dataset.ideaCreated || "",
        category: (card) => (card.dataset.ideaCategory || "").toLowerCase(),
        team: (card) => (card.dataset.ideaTeam || "").toLowerCase(),
        title: (card) => (card.dataset.ideaTitle || "").toLowerCase(),
      };
      const left = map[sortBy](a);
      const right = map[sortBy](b);
      if (left < right) return direction === "asc" ? -1 : 1;
      if (left > right) return direction === "asc" ? 1 : -1;
      return 0;
    });
    sorted.forEach((card) => list.appendChild(card));
  }

  function initMaster() {
    const ideasPanel = $("[data-ideas-panel]");
    const sort = $("[data-ideas-sort]");
    const direction = $("[data-ideas-direction]");

    const tabName = getTabName();
    activateTab(tabName);
    if (sort) sort.value = getStoredIdeaSort();
    if (direction) direction.value = getStoredIdeaDirection();
    if (ideasPanel) ideasPanel.classList.toggle("compact-ideas", isIdeasCompact());
    applyIdeasSort();
    applyIdeaDisplayMode();
    updateIdeaDescriptionVisibility();

    if (sort) sort.onchange = () => {
      localStorage.setItem("bir-idea-sort", sort.value);
      applyIdeasSort();
    };
    if (direction) direction.onchange = () => {
      localStorage.setItem("bir-idea-direction", direction.value);
      applyIdeasSort();
    };

    const descriptionToggle = $("[data-ideas-toggle-description]");
    if (descriptionToggle) {
      descriptionToggle.onclick = () => {
        const next = isIdeaDescriptionShown() ? "0" : "1";
        localStorage.setItem("bir-ideas-show-description", next);
        updateIdeaDescriptionVisibility();
      };
    }

    const toggle = $("[data-ideas-toggle-details]");
    if (toggle) toggle.onclick = () => {
      const panel = $("[data-ideas-panel]");
      panel?.classList.toggle("compact-ideas");
      localStorage.setItem("bir-ideas-compact", panel?.classList.contains("compact-ideas") ? "1" : "0");
      applyIdeaDisplayMode();
    };

    const bracketSelect = $("[data-bracket-select]");
    const bracketHidden = $("[data-bracket-edit-id]");
    if (bracketSelect && bracketHidden) {
      bracketSelect.onchange = () => {
        bracketHidden.value = bracketSelect.value;
      };
    }
  }

  function init(page) {
    state.currentPage = page || document.body.dataset.page || "";
    installGlobalHandlers();
    startPolling();
    dismissResetAlertAfterDelay();
    if (state.currentPage === "master") {
      initMaster();
    }
  }

  window.BIRApp = {
    init,
    api,
    refreshLiveRoot,
    pollState,
    activateTab,
  };

  document.addEventListener("DOMContentLoaded", () => {
    init(document.body.dataset.page || "");
  });
})();
