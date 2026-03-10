(function () {
  const root = document.getElementById("lunar-page")
  if (!root) {
    return
  }

  const checkpointsSeed = JSON.parse(document.getElementById("lunar-checkpoints-seed").textContent)
  const jobsSeed = JSON.parse(document.getElementById("lunar-jobs-seed").textContent)
  const sourceSeed = JSON.parse(document.getElementById("lunar-training-source-seed").textContent)

  const urls = {
    createSession: root.dataset.createSessionUrl,
    stepSession: root.dataset.stepSessionTemplate,
    resetSession: root.dataset.resetSessionTemplate,
    deleteSession: root.dataset.deleteSessionTemplate,
    checkpoints: root.dataset.checkpointsUrl,
    checkpointSummary: root.dataset.checkpointSummaryTemplate,
    jobs: root.dataset.jobsUrl,
    jobsList: root.dataset.jobsListUrl,
    job: root.dataset.jobTemplate,
  }

  const stageImage = document.getElementById("lunarStageImage")
  const stageStatus = document.getElementById("lunarStageStatus")
  const stageEyebrow = document.querySelector("[data-stage-eyebrow]")
  const stageTitle = document.querySelector("[data-stage-title]")
  const telemetryNodes = Object.fromEntries(
    Array.from(document.querySelectorAll("[data-telemetry]")).map((node) => [node.dataset.telemetry, node])
  )
  const stateGrid = document.getElementById("lunarStateGrid")
  const checkpointSelect = document.getElementById("checkpointSelect")
  const checkpointSummary = document.getElementById("checkpointSummary")
  const jobList = document.getElementById("jobList")
  const jobLogViewer = document.getElementById("jobLogViewer")
  const machineSpeed = document.getElementById("machineSpeed")
  const playNewSessionBtn = document.getElementById("playNewSessionBtn")
  const playResetBtn = document.getElementById("playResetBtn")
  const machineCreateBtn = document.getElementById("machineCreateBtn")
  const machineRunBtn = document.getElementById("machineRunBtn")
  const machinePauseBtn = document.getElementById("machinePauseBtn")
  const machineStepBtn = document.getElementById("machineStepBtn")
  const machineResetBtn = document.getElementById("machineResetBtn")
  const trainSubmitBtn = document.getElementById("trainSubmitBtn")
  const editorResetBtn = document.getElementById("editorResetBtn")
  const evaluateCheckpointBtn = document.getElementById("evaluateCheckpointBtn")
  const actionButtons = Array.from(document.querySelectorAll(".action-btn"))
  const tabButtons = Array.from(document.querySelectorAll("[data-tab]"))
  const tabPanels = Array.from(document.querySelectorAll("[data-panel]"))
  const runtimeStatus = document.querySelector("[data-runtime-status]")

  const editorHost = document.getElementById("lunarEditor")
  const editorFallback = document.getElementById("lunarEditorFallback")
  let aceEditor = null
  if (window.ace && editorHost) {
    aceEditor = window.ace.edit(editorHost)
    aceEditor.session.setMode("ace/mode/python")
    aceEditor.setTheme("ace/theme/textmate")
    aceEditor.setValue(sourceSeed, -1)
    editorFallback.style.display = "none"
  } else {
    editorHost.style.display = "none"
    editorFallback.value = sourceSeed
  }

  const model = {
    currentTab: "play",
    playSession: null,
    machineSession: null,
    machineRunning: false,
    machineTimer: null,
    selectedJobId: null,
    checkpoints: checkpointsSeed,
    jobs: jobsSeed,
  }

  function buildUrl(template, token, value) {
    return String(template || "").replace(token, encodeURIComponent(String(value)))
  }

  function getEditorValue() {
    return aceEditor ? aceEditor.getValue() : editorFallback.value
  }

  function setEditorValue(source) {
    if (aceEditor) {
      aceEditor.setValue(source, -1)
      return
    }
    editorFallback.value = source
  }

  function setStageMode(mode) {
    model.currentTab = mode
    tabButtons.forEach((button) => {
      button.classList.toggle("is-active", button.dataset.tab === mode)
    })
    tabPanels.forEach((panel) => {
      panel.classList.toggle("is-active", panel.dataset.panel === mode)
    })
    if (mode === "play") {
      stageEyebrow.textContent = "Human Control"
      stageTitle.textContent = "Fly the lander yourself"
    } else if (mode === "machine") {
      stageEyebrow.textContent = "Machine Play"
      stageTitle.textContent = "Inspect a controller on the real environment"
    } else {
      stageEyebrow.textContent = "Training"
      stageTitle.textContent = "Run a bounded DQN job and reuse the checkpoint"
    }
  }

  function setStageStatus(message) {
    stageStatus.textContent = message
  }

  function renderStateGrid(labels, values) {
    const pairs = labels.map((label, index) => {
      const value = values && values[index] !== undefined ? values[index] : "-"
      return `
        <article class="state-card">
          <span class="metric-label">${label}</span>
          <strong>${value}</strong>
        </article>
      `
    })
    stateGrid.innerHTML = pairs.join("")
  }

  function renderTelemetry(payload) {
    stageImage.src = payload.frame
    telemetryNodes.step_index.textContent = String(payload.step_index)
    telemetryNodes.reward.textContent = String(payload.reward)
    telemetryNodes.score.textContent = String(payload.score)
    telemetryNodes.action.textContent = payload.action ? payload.action.label : "-"
    telemetryNodes.done.textContent = String(payload.done)
    telemetryNodes.truncated.textContent = String(payload.truncated)
    renderStateGrid(payload.state_labels || [], payload.state || [])
  }

  function renderCheckpoints() {
    checkpointSelect.innerHTML = ""
    model.checkpoints.forEach((checkpoint) => {
      const option = document.createElement("option")
      option.value = checkpoint.id
      option.textContent = checkpoint.featured ? `${checkpoint.label} (Featured)` : checkpoint.label
      checkpointSelect.appendChild(option)
    })
    if (!checkpointSelect.value && model.checkpoints.length) {
      checkpointSelect.value = model.checkpoints[0].id
    }
    updateCheckpointSummary()
  }

  function renderJobs() {
    if (!model.jobs.length) {
      jobList.innerHTML = '<p class="panel-note">No jobs yet.</p>'
      if (!model.selectedJobId) {
        jobLogViewer.textContent = "No job selected."
      }
      return
    }
    jobList.innerHTML = model.jobs
      .map((job) => {
        const selectedClass = model.selectedJobId === job.id ? " is-selected" : ""
        return `
          <button class="job-chip${selectedClass}" type="button" data-job-id="${job.id}">
            <strong>#${job.id}</strong>
            <span>${job.kind}</span>
            <span>${job.status}</span>
          </button>
        `
      })
      .join("")

    Array.from(jobList.querySelectorAll("[data-job-id]")).forEach((button) => {
      button.addEventListener("click", () => {
        model.selectedJobId = Number(button.dataset.jobId)
        renderJobs()
        updateJobDetails()
      })
    })

    if (!model.selectedJobId) {
      model.selectedJobId = model.jobs[0].id
      renderJobs()
      updateJobDetails()
    }
  }

  function updateJobDetails() {
    const job = model.jobs.find((item) => item.id === model.selectedJobId)
    if (!job) {
      jobLogViewer.textContent = "No job selected."
      return
    }
    const lines = []
    lines.push(`job #${job.id} | ${job.kind} | ${job.status}`)
    if (job.summary) {
      lines.push("")
      lines.push("summary:")
      lines.push(JSON.stringify(job.summary, null, 2))
    }
    if (job.metrics_tail && job.metrics_tail.length) {
      lines.push("")
      lines.push("recent metrics:")
      lines.push(JSON.stringify(job.metrics_tail, null, 2))
    }
    if (job.stdout_tail) {
      lines.push("")
      lines.push("stdout:")
      lines.push(job.stdout_tail)
    }
    if (job.stderr_tail) {
      lines.push("")
      lines.push("stderr:")
      lines.push(job.stderr_tail)
    }
    jobLogViewer.textContent = lines.join("\n")
  }

  async function fetchJson(url, options) {
    const response = await fetch(url, {
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      ...(options || {}),
    })
    const body = await response.json()
    if (!response.ok) {
      throw new Error(body.error || `request failed: ${response.status}`)
    }
    return body
  }

  async function refreshJobs() {
    const body = await fetchJson(urls.jobsList)
    model.jobs = body.jobs
    renderJobs()
    if (model.jobs.some((job) => job.status === "completed")) {
      await refreshCheckpoints()
    }
  }

  async function refreshCheckpoints() {
    const body = await fetchJson(urls.checkpoints)
    model.checkpoints = body.checkpoints
    renderCheckpoints()
  }

  async function updateCheckpointSummary() {
    const selectedId = checkpointSelect.value
    if (!selectedId) {
      checkpointSummary.textContent = "No controller selected."
      return
    }
    const checkpoint = model.checkpoints.find((item) => item.id === selectedId)
    if (selectedId === "heuristic-baseline") {
      checkpointSummary.textContent = checkpoint.note
      return
    }
    const url = buildUrl(urls.checkpointSummary, "CHECKPOINT_ID", selectedId)
    try {
      const body = await fetchJson(url)
      const summary = body.checkpoint
      const training = summary.training_summary || {}
      const evaluation = summary.evaluation_summary || {}
      checkpointSummary.textContent =
        `Algorithm: ${training.algorithm || "dqn"} | ` +
        `Best score: ${training.best_score ?? "n/a"} | ` +
        `Episodes: ${training.episodes_completed ?? "n/a"} | ` +
        `Eval mean: ${evaluation.mean_score ?? "not evaluated"}`
    } catch (error) {
      checkpointSummary.textContent = error.message
    }
  }

  async function createSession(controller, checkpointId) {
    const payload = { controller }
    if (checkpointId) {
      payload.checkpoint_id = checkpointId
    }
    return fetchJson(urls.createSession, {
      method: "POST",
      body: JSON.stringify(payload),
    })
  }

  async function stepSession(sessionId, action) {
    const url = buildUrl(urls.stepSession, "SESSION_ID", sessionId)
    const payload = action === undefined ? {} : { action }
    return fetchJson(url, {
      method: "POST",
      body: JSON.stringify(payload),
    })
  }

  async function resetSession(sessionId) {
    const url = buildUrl(urls.resetSession, "SESSION_ID", sessionId)
    return fetchJson(url, {
      method: "POST",
      body: "{}",
    })
  }

  async function deleteSession(sessionId) {
    const url = buildUrl(urls.deleteSession, "SESSION_ID", sessionId)
    return fetchJson(url, { method: "DELETE" })
  }

  async function ensurePlaySession() {
    if (model.playSession) {
      return model.playSession
    }
    const payload = await createSession("human")
    model.playSession = payload.session.id
    renderTelemetry(payload)
    setStageStatus("Human session ready.")
    return model.playSession
  }

  async function ensureMachineSession() {
    if (model.machineSession) {
      return model.machineSession
    }
    const selectedId = checkpointSelect.value
    const controller = selectedId === "heuristic-baseline" ? "heuristic" : "checkpoint"
    const payload = await createSession(controller, controller === "checkpoint" ? selectedId : null)
    model.machineSession = payload.session.id
    renderTelemetry(payload)
    setStageStatus(`Machine session ready: ${selectedId}.`)
    return model.machineSession
  }

  async function runMachineStep() {
    if (!model.machineSession) {
      await ensureMachineSession()
    }
    const payload = await stepSession(model.machineSession)
    renderTelemetry(payload)
    if (payload.done || payload.truncated) {
      model.machineRunning = false
      setStageStatus("Machine session reached a terminal state. Reset or load a new controller.")
    }
  }

  function scheduleMachineLoop() {
    window.clearTimeout(model.machineTimer)
    if (!model.machineRunning) {
      return
    }
    const speed = Number(machineSpeed.value)
    const delay = Math.max(50, 520 - speed * 35)
    model.machineTimer = window.setTimeout(async () => {
      try {
        await runMachineStep()
      } catch (error) {
        model.machineRunning = false
        setStageStatus(error.message)
      }
      scheduleMachineLoop()
    }, delay)
  }

  async function submitJob(kind, extra) {
    const payload = { kind, ...(extra || {}) }
    const body = await fetchJson(urls.jobs, {
      method: "POST",
      body: JSON.stringify(payload),
    })
    await refreshJobs()
    return body.job
  }

  tabButtons.forEach((button) => {
    button.addEventListener("click", () => setStageMode(button.dataset.tab))
  })

  checkpointSelect.addEventListener("change", () => {
    model.machineSession = null
    updateCheckpointSummary()
  })

  playNewSessionBtn.addEventListener("click", async () => {
    if (model.playSession) {
      await deleteSession(model.playSession).catch(() => null)
      model.playSession = null
    }
    try {
      setStageMode("play")
      await ensurePlaySession()
    } catch (error) {
      setStageStatus(error.message)
    }
  })

  playResetBtn.addEventListener("click", async () => {
    if (!model.playSession) {
      return
    }
    try {
      setStageMode("play")
      const payload = await resetSession(model.playSession)
      renderTelemetry(payload)
      setStageStatus("Human session reset.")
    } catch (error) {
      setStageStatus(error.message)
    }
  })

  actionButtons.forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        setStageMode("play")
        const sessionId = await ensurePlaySession()
        const payload = await stepSession(sessionId, Number(button.dataset.action))
        renderTelemetry(payload)
        setStageStatus(`Played ${payload.action ? payload.action.label : "action"}.`)
      } catch (error) {
        setStageStatus(error.message)
      }
    })
  })

  machineCreateBtn.addEventListener("click", async () => {
    try {
      setStageMode("machine")
      if (model.machineSession) {
        await deleteSession(model.machineSession).catch(() => null)
        model.machineSession = null
      }
      await ensureMachineSession()
    } catch (error) {
      setStageStatus(error.message)
    }
  })

  machineRunBtn.addEventListener("click", async () => {
    try {
      setStageMode("machine")
      await ensureMachineSession()
      model.machineRunning = true
      setStageStatus("Machine playback running.")
      scheduleMachineLoop()
    } catch (error) {
      setStageStatus(error.message)
    }
  })

  machinePauseBtn.addEventListener("click", () => {
    model.machineRunning = false
    window.clearTimeout(model.machineTimer)
    setStageStatus("Machine playback paused.")
  })

  machineStepBtn.addEventListener("click", async () => {
    try {
      setStageMode("machine")
      model.machineRunning = false
      window.clearTimeout(model.machineTimer)
      await runMachineStep()
      setStageStatus("Stepped the machine controller once.")
    } catch (error) {
      setStageStatus(error.message)
    }
  })

  machineResetBtn.addEventListener("click", async () => {
    if (!model.machineSession) {
      return
    }
    try {
      setStageMode("machine")
      model.machineRunning = false
      const payload = await resetSession(model.machineSession)
      renderTelemetry(payload)
      setStageStatus("Machine session reset.")
    } catch (error) {
      setStageStatus(error.message)
    }
  })

  trainSubmitBtn.addEventListener("click", async () => {
    try {
      setStageMode("training")
      runtimeStatus.textContent = "Training job queued"
      await submitJob("train", { source: getEditorValue() })
      setStageStatus("Training job submitted.")
    } catch (error) {
      setStageStatus(error.message)
    }
  })

  editorResetBtn.addEventListener("click", () => {
    setEditorValue(sourceSeed)
    setStageStatus("Training template restored.")
  })

  evaluateCheckpointBtn.addEventListener("click", async () => {
    const checkpointId = checkpointSelect.value
    if (!checkpointId || checkpointId === "heuristic-baseline") {
      setStageStatus("Pick a trained checkpoint before submitting an evaluation job.")
      return
    }
    try {
      setStageMode("training")
      await submitJob("evaluate", {
        checkpoint_id: checkpointId,
        params: { episodes: 20 },
      })
      setStageStatus(`Evaluation job submitted for ${checkpointId}.`)
    } catch (error) {
      setStageStatus(error.message)
    }
  })

  window.addEventListener("keydown", async (event) => {
    if (model.currentTab !== "play") {
      return
    }
    const tag = String(document.activeElement && document.activeElement.tagName || "").toLowerCase()
    if (tag === "textarea" || tag === "input") {
      return
    }
    const keyMap = {
      " ": 0,
      ArrowLeft: 1,
      ArrowUp: 2,
      ArrowRight: 3,
    }
    const action = keyMap[event.key]
    if (action === undefined || event.repeat) {
      return
    }
    event.preventDefault()
    try {
      const sessionId = await ensurePlaySession()
      const payload = await stepSession(sessionId, action)
      renderTelemetry(payload)
      setStageStatus(`Keyboard action: ${payload.action ? payload.action.label : "-"}.`)
    } catch (error) {
      setStageStatus(error.message)
    }
  })

  renderStateGrid(["x", "y", "vx", "vy", "angle", "angular_velocity", "left_leg_contact", "right_leg_contact"], [])
  renderCheckpoints()
  renderJobs()
  setStageMode("play")
  runtimeStatus.textContent = "Runtime ready"
  window.setInterval(() => {
    refreshJobs().catch(() => null)
  }, 4000)
})()
