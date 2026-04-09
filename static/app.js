(() => {
  const state = {
    currentPage: "",
    pollTimer: null,
    lastVersion: null,
    globalInstalled: false,
    draggedTeamId: null,
    draggedLeaderId: null,
    draggedIdeaId: null,
    draggedOutput: null,
    draggedMatchupId: null,
    pendingIdeaBracketId: null,
    pendingSeedBracketId: null,
    pendingSeedInitialOrder: [],
    pendingSeedHasPlayed: false,
    cooldownUiTimer: null,
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
          openBracketModal(card);
        }
        return;
      }

      const bracketSeed = event.target.closest("[data-bracket-seed]");
      if (bracketSeed) {
        const card = bracketSeed.closest("[data-bracket-card]");
        if (card) {
          openSeedModal(card);
        }
        return;
      }

      const bracketModalClose = event.target.closest("[data-bracket-modal-close]");
      if (bracketModalClose) {
        closeBracketModal();
        return;
      }

      const seedModalClose = event.target.closest("[data-seed-modal-close]");
      if (seedModalClose) {
        closeSeedModal();
        return;
      }

      const seedMoveUp = event.target.closest("[data-seed-up]");
      if (seedMoveUp) {
        const row = seedMoveUp.closest("[data-seed-item]");
        if (!row || !row.previousElementSibling) return;
        row.parentElement.insertBefore(row, row.previousElementSibling);
        refreshSeedPositions();
        refreshSeedPreviews();
        return;
      }

      const seedMoveDown = event.target.closest("[data-seed-down]");
      if (seedMoveDown) {
        const row = seedMoveDown.closest("[data-seed-item]");
        if (!row || !row.nextElementSibling) return;
        row.parentElement.insertBefore(row.nextElementSibling, row);
        refreshSeedPositions();
        refreshSeedPreviews();
        return;
      }

      const seedSave = event.target.closest("[data-seed-save]");
      if (seedSave) {
        await saveSeedOrder();
        return;
      }

      const removeIdea = event.target.closest("[data-remove-idea]");
      if (removeIdea) {
        const ideaId = removeIdea.dataset.ideaId;
        if (!ideaId) return;
        await api("delete_idea", { idea_id: ideaId });
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

      const apiActionButton = event.target.closest("[data-api-action]");
      if (apiActionButton) {
        const action = apiActionButton.dataset.apiAction;
        if (!action || apiActionButton.disabled) {
          return;
        }
        if (action === "remove_round") {
          const ok = window.confirm("Delete the last round and its stage? This cannot be undone.");
          if (!ok) {
            return;
          }
        }
        await api(action, {});
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
      await api(action, payload);
      if (action === "update_leader") closeLeaderModal();
      if (action === "update_idea") closeIdeaModal();
    });

    document.addEventListener("dragstart", (event) => {
      const seedRow = event.target.closest("[data-seed-item]");
      if (seedRow && state.pendingSeedBracketId) {
        event.dataTransfer?.setData("text/plain", `seed:${seedRow.dataset.ideaId}`);
        state.draggedIdeaId = seedRow.dataset.ideaId || null;
        return;
      }
      const teamRow = event.target.closest("[data-team-row]");
      const leaderCard = event.target.closest("[data-leader-card]");
      const ideaCard = event.target.closest("[data-idea-card], [data-idea-chip]");
      const outputChip = event.target.closest("[data-output-chip]");
      const matchupCard = event.target.closest("[data-matchup-card]");

      if (teamRow) {
        state.draggedTeamId = teamRow.dataset.teamId;
        event.dataTransfer?.setData("text/plain", `team:${state.draggedTeamId}`);
      } else if (leaderCard) {
        state.draggedLeaderId = leaderCard.dataset.leaderId;
        event.dataTransfer?.setData("text/plain", `leader:${state.draggedLeaderId}`);
      } else if (ideaCard) {
        state.draggedIdeaId = ideaCard.dataset.ideaId;
        event.dataTransfer?.setData("text/plain", `idea:${state.draggedIdeaId}`);
      } else if (outputChip) {
        const sourceBracketId = outputChip.dataset.sourceBracketId;
        const outputSlot = outputChip.dataset.outputSlot;
        state.draggedOutput = { sourceBracketId, outputSlot };
        event.dataTransfer?.setData("text/plain", `output:${sourceBracketId}:${outputSlot}`);
      } else if (matchupCard) {
        state.draggedMatchupId = matchupCard.dataset.matchupId || null;
        event.dataTransfer?.setData("text/plain", `matchup:${state.draggedMatchupId}`);
      }
    });

    document.addEventListener("dragover", (event) => {
      if (event.target.closest("[data-seed-item], [data-team-row], [data-team-column], [data-bracket-card], [data-round-dropzone], [data-matchup-card]")) {
        event.preventDefault();
      }
    });

    document.addEventListener("drop", async (event) => {
      const seedRow = event.target.closest("[data-seed-item]");
      const teamRow = event.target.closest("[data-team-row]");
      const teamColumn = event.target.closest("[data-team-column]");
      const bracketCard = event.target.closest("[data-bracket-card]");
      const roundDropzone = event.target.closest("[data-round-dropzone]");
      const matchupCard = event.target.closest("[data-matchup-card]");
      const payloadText = event.dataTransfer?.getData("text/plain") || "";

      if (seedRow && payloadText.startsWith("seed:") && state.pendingSeedBracketId) {
        event.preventDefault();
        const draggedId = payloadText.split(":")[1];
        const rows = $all("[data-seed-item]");
        const draggedRow = rows.find((row) => row.dataset.ideaId === draggedId);
        if (draggedRow && draggedRow !== seedRow) {
          seedRow.parentElement.insertBefore(draggedRow, seedRow);
          refreshSeedPositions();
          refreshSeedPreviews();
        }
        return;
      }

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

      if (bracketCard && payloadText.startsWith("output:") && state.draggedOutput) {
        event.preventDefault();
        const targetBracketId = bracketCard.dataset.bracketId;
        const { sourceBracketId, outputSlot } = state.draggedOutput;
        if (sourceBracketId && outputSlot && targetBracketId && sourceBracketId !== targetBracketId) {
          await api("clone_output_to_bracket", {
            source_bracket_id: sourceBracketId,
            slot: outputSlot,
            target_bracket_id: targetBracketId,
          });
        }
        state.draggedOutput = null;
      }

      if (roundDropzone && !matchupCard && payloadText.startsWith("matchup:") && state.draggedMatchupId) {
        event.preventDefault();
        await api("assign_matchup_to_round", {
          matchup_id: state.draggedMatchupId,
          round_id: roundDropzone.dataset.roundId,
        });
        state.draggedMatchupId = null;
        return;
      }

      if (matchupCard && payloadText.startsWith("matchup:") && state.draggedMatchupId) {
        event.preventDefault();
        const source = $(`[data-matchup-card][data-matchup-id='${state.draggedMatchupId}']`);
        const sourceRound = source?.closest("[data-round-dropzone]");
        const targetRound = matchupCard.closest("[data-round-dropzone]");

        if (targetRound) {
          const targetRoundId = targetRound.dataset.roundId;
          if (!targetRoundId) {
            state.draggedMatchupId = null;
            return;
          }
          if (!sourceRound || sourceRound.dataset.roundId !== targetRoundId) {
            await api("assign_matchup_to_round", {
              matchup_id: state.draggedMatchupId,
              round_id: targetRoundId,
            });
          }
          if (source && source !== matchupCard) {
            targetRound.insertBefore(source, matchupCard);
          }
          const roundOrdered = $all("[data-matchup-card]", targetRound)
            .map((card) => card.dataset.matchupId)
            .filter(Boolean);
          await api("reorder_round_matchups", {
            round_id: targetRoundId,
            matchup_ids: roundOrdered,
          });
          state.draggedMatchupId = null;
          return;
        }

        const list = $("[data-matchups-column]");
        const sourceInList = $(`[data-matchup-card][data-matchup-id='${state.draggedMatchupId}']`, list || document);
        if (list && sourceInList && sourceInList !== matchupCard) {
          list.insertBefore(sourceInList, matchupCard);
          const ordered = $all("[data-matchup-card]", list).map((card) => card.dataset.matchupId).filter(Boolean);
          await api("reorder_matchups", { matchup_ids: ordered });
        }
        state.draggedMatchupId = null;
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
    const assigned_leader_field = $("[data-idea-assigned-leader-field]", modal);
    const assigned_team_field = $("[data-idea-assigned-team-field]", modal);
    const point_miranda_field = $("[data-idea-point-miranda-field]", modal);
    const point_kirrawee_field = $("[data-idea-point-kirrawee-field]", modal);
    const backup_miranda_field = $("[data-idea-backup-miranda-field]", modal);
    const backup_kirrawee_field = $("[data-idea-backup-kirrawee-field]", modal);
    if (assigned_leader_field) assigned_leader_field.value = card.dataset.ideaAssignedLeaderId || "";
    if (assigned_team_field) assigned_team_field.value = card.dataset.ideaAssignedTeamId || "";
    if (point_miranda_field) point_miranda_field.value = card.dataset.ideaPointMiranda || "";
    if (point_kirrawee_field) point_kirrawee_field.value = card.dataset.ideaPointKirrawee || "";
    if (backup_miranda_field) backup_miranda_field.value = card.dataset.ideaBackupMiranda || "";
    if (backup_kirrawee_field) backup_kirrawee_field.value = card.dataset.ideaBackupKirrawee || "";
    $("[data-idea-bracket-field]", modal).value = card.dataset.ideaBracketId || "";
    modal.classList.remove("hidden");
  }

  function closeIdeaModal() {
    const modal = $("[data-idea-modal]");
    if (modal) modal.classList.add("hidden");
  }

  function openBracketModal(card) {
    const modal = $("[data-bracket-modal]");
    if (!modal) return;
    $("[data-bracket-edit-id]", modal).value = card.dataset.bracketId || "";
    $("[data-bracket-edit-name]", modal).value = card.dataset.bracketName || "";
    $("[data-bracket-edit-type]", modal).value = card.dataset.bracketType || "";
    $("[data-bracket-edit-description]", modal).value = card.dataset.bracketDescription || "";
    $("[data-bracket-edit-output-count]", modal).value = card.dataset.bracketOutputCount || 0;
    modal.classList.remove("hidden");
  }

  function closeBracketModal() {
    const modal = $("[data-bracket-modal]");
    if (modal) modal.classList.add("hidden");
  }

  function openSeedModal(card) {
    const modal = $("[data-seed-modal]");
    if (!modal) return;
    state.pendingSeedBracketId = card.dataset.bracketId || null;
    state.pendingSeedHasPlayed = Number(card.dataset.bracketPlayed || "0") > 0;
    const title = $("[data-seed-title]", modal);
    if (title) title.textContent = `Seed ${card.dataset.bracketName || "Bracket"}`;

    const seedList = $("[data-seed-list]", modal);
    const schedulePreview = $("[data-seed-schedule-preview]", modal);
    const matchPreview = $("[data-seed-match-preview]", modal);
    if (seedList) seedList.innerHTML = "";
    if (schedulePreview) schedulePreview.innerHTML = "";
    if (matchPreview) matchPreview.innerHTML = "";

    const ideas = $all("[data-idea-chip]", card);
    state.pendingSeedInitialOrder = ideas.map((chip) => chip.dataset.ideaId || "").filter(Boolean);
    ideas.forEach((chip, index) => {
      const row = document.createElement("div");
      row.className = "seed-row";
      row.dataset.seedItem = "1";
      row.dataset.ideaId = chip.dataset.ideaId || "";
      row.draggable = true;
      row.innerHTML = `
        <span class="seed-position">${index + 1}</span>
        <span class="seed-title">${chip.querySelector("span")?.textContent?.trim() || chip.textContent.trim()}</span>
        <div class="inline-actions">
          <button type="button" class="secondary" data-seed-up>↑</button>
          <button type="button" class="secondary" data-seed-down>↓</button>
        </div>
      `;
      seedList?.appendChild(row);
    });

    const previewLines = buildSeedPreviewLines(card, ideas.map((chip) => chip.textContent.trim()));
    previewLines.schedule.forEach((line) => {
      const div = document.createElement("div");
      div.textContent = line;
      schedulePreview?.appendChild(div);
    });
    previewLines.matches.forEach((line) => {
      const div = document.createElement("div");
      div.textContent = line;
      matchPreview?.appendChild(div);
    });

    modal.classList.remove("hidden");
  }

  function refreshSeedPositions() {
    $all("[data-seed-item]").forEach((row, index) => {
      const pos = $(".seed-position", row);
      if (pos) pos.textContent = String(index + 1);
    });
  }

  function refreshSeedPreviews() {
    const modal = $("[data-seed-modal]");
    if (!modal) return;
    const bracketCard = $("[data-bracket-card][data-bracket-id='" + state.pendingSeedBracketId + "']");
    if (!bracketCard) return;
    const labels = $all("[data-seed-item]", modal).map((row) => $(".seed-title", row)?.textContent?.trim() || row.dataset.ideaId || "");
    const previewLines = buildSeedPreviewLines(bracketCard, labels);
    const schedulePreview = $("[data-seed-schedule-preview]", modal);
    const matchPreview = $("[data-seed-match-preview]", modal);
    if (schedulePreview) schedulePreview.innerHTML = "";
    if (matchPreview) matchPreview.innerHTML = "";
    previewLines.schedule.forEach((line) => {
      const div = document.createElement("div");
      div.textContent = line;
      schedulePreview?.appendChild(div);
    });
    previewLines.matches.forEach((line) => {
      const div = document.createElement("div");
      div.textContent = line;
      matchPreview?.appendChild(div);
    });
  }

  function closeSeedModal() {
    const modal = $("[data-seed-modal]");
    if (modal) modal.classList.add("hidden");
    state.pendingSeedBracketId = null;
  }

  function buildSeedPreviewLines(card, labels) {
    const bracketType = card.dataset.bracketType || "";
    if (bracketType.includes("Elimination")) {
      const schedule = [];
      const matches = [];
      let current = labels.map((name, idx) => `Seed ${idx + 1}: ${name}`);
      let round = 1;
      while (current.length > 1) {
        schedule.push(`Round ${round}`);
        const next = [];
        for (let i = 0; i < current.length; i += 2) {
          if (i + 1 < current.length) {
            schedule.push(`  ${current[i]} vs ${current[i + 1]}`);
            matches.push(`Match ${matches.length + 1}: ${current[i]} vs ${current[i + 1]}`);
            next.push(`Winner of (${current[i]} vs ${current[i + 1]})`);
          } else {
            schedule.push(`  ${current[i]} (bye)`);
            matches.push(`Match ${matches.length + 1}: ${current[i]} (bye)`);
            next.push(current[i]);
          }
        }
        current = next;
        round += 1;
      }
      return { schedule, matches };
    }
    if (bracketType === "Round Robin" || bracketType === "Swiss") {
      const schedule = [];
      const matches = [];
      for (let i = 0; i < labels.length; i += 2) {
        if (i + 1 < labels.length) {
          schedule.push(`Seed ${i + 1} vs Seed ${i + 2}`);
          matches.push(`Match ${Math.floor(i / 2) + 1}: ${labels[i]} vs ${labels[i + 1]}`);
        } else {
          schedule.push(`Seed ${i + 1} (bye)`);
          matches.push(`Match ${Math.floor(i / 2) + 1}: ${labels[i]} (bye)`);
        }
      }
      return { schedule, matches };
    }
    return { schedule: ["No preview available."], matches: ["No preview available."] };
  }

  async function saveSeedOrder() {
    if (!state.pendingSeedBracketId) return;
    const orderedIdeaIds = $all("[data-seed-item]").map((row) => row.dataset.ideaId).filter(Boolean);
    const changed = orderedIdeaIds.join("|") !== state.pendingSeedInitialOrder.join("|");
    if (changed && state.pendingSeedHasPlayed && !window.confirm("One or more affected ideas have already played in a match, saving will reset their progress. Are you sure you want to continue?")) {
      return;
    }
    await api("set_bracket_seed_order", {
      bracket_id: state.pendingSeedBracketId,
      ordered_idea_ids: orderedIdeaIds,
    });
    closeSeedModal();
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

  function dismissAlertsAfterDelay() {
    const alerts = $all(".alert");
    alerts.forEach((alert) => {
      window.setTimeout(() => {
        alert.remove();
      }, 3000);
    });
  }

  function initCooldownUi() {
    if (state.cooldownUiTimer) {
      clearInterval(state.cooldownUiTimer);
      state.cooldownUiTimer = null;
    }

    const tick = () => {
      const now = Date.now() / 1000;
      const countdownLabels = $all("[data-matchup-countdown-end]");
      countdownLabels.forEach((label) => {
        const paused = label.dataset.matchupCountdownPaused === "1";
        const end = Number(label.dataset.matchupCountdownEnd || "0");
        if (!end) return;
        if (paused) {
          label.textContent = "Paused";
          return;
        }
        const remaining = Math.max(0, Math.ceil(end - now));
        label.textContent = `${remaining}s`;
      });

      const labels = $all("[data-cooldown-label]");
      labels.forEach((label) => {
        const until = Number(label.dataset.cooldownUntil || "0");
        const remaining = Math.max(0, until - now);
        if (remaining > 0.05) {
          label.classList.remove("hidden");
          label.textContent = `Cooldown: ${remaining.toFixed(1)}s`;
        } else {
          label.classList.add("hidden");
          label.textContent = "";
        }
      });

      const buttons = $all("[data-cooldown-button]");
      buttons.forEach((button) => {
        const until = Number(button.dataset.cooldownUntil || "0");
        const duration = Number(button.dataset.cooldownDuration || "3");
        const remaining = Math.max(0, until - now);
        const progress = remaining > 0 ? Math.max(0, Math.min(100, ((duration - remaining) / duration) * 100)) : 100;
        button.style.setProperty("--cooldown-progress", `${progress}%`);
        button.disabled = remaining > 0.05;
      });
    };

    tick();
    if ($all("[data-cooldown-button], [data-cooldown-label]").length) {
      state.cooldownUiTimer = setInterval(tick, 100);
    }
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

    // Bracket edit and seed are handled by modal UI.
  }

  function init(page) {
    state.currentPage = page || document.body.dataset.page || "";
    installGlobalHandlers();
    startPolling();
    dismissAlertsAfterDelay();
    if (state.currentPage === "master") {
      initMaster();
    }
    initCooldownUi();
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
