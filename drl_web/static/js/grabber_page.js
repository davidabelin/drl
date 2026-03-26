(function () {
  const root = document.getElementById("grabber-page")
  if (!root) {
    return
  }

  const checkpointsSeed = JSON.parse(document.getElementById("grabber-checkpoints-seed").textContent)
  const jobsSeed = JSON.parse(document.getElementById("grabber-jobs-seed").textContent)
  const trainingDefaults = JSON.parse(document.getElementById("grabber-training-form-seed").textContent)

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
    timeline: root.dataset.timelineTemplate,
    timelineSnapshot: root.dataset.timelineSnapshotTemplate,
  }

  const stageCanvas = document.getElementById("grabberStageCanvas")
  const ctx = stageCanvas.getContext("2d")
  const stageStatus = document.getElementById("grabberStageStatus")
  const stageEyebrow = document.querySelector("[data-stage-eyebrow]")
  const stageTitle = document.querySelector("[data-stage-title]")
  const runtimeStatus = document.querySelector("[data-runtime-status]")
  const telemetryNodes = Object.fromEntries(
    Array.from(document.querySelectorAll("[data-telemetry]")).map((node) => [node.dataset.telemetry, node])
  )
  const gaugeValues = Array.from(document.querySelectorAll("[data-gauge-value]"))
  const gaugeFills = Array.from(document.querySelectorAll("[data-gauge-fill]"))
  const rewardGrid = document.getElementById("rewardGrid")
  const observationGrid = document.getElementById("observationGrid")
  const checkpointSelect = document.getElementById("checkpointSelect")
  const checkpointSummary = document.getElementById("checkpointSummary")
  const playNewSessionBtn = document.getElementById("playNewSessionBtn")
  const playResetBtn = document.getElementById("playResetBtn")
  const machineCreateBtn = document.getElementById("machineCreateBtn")
  const machineRunBtn = document.getElementById("machineRunBtn")
  const machinePauseBtn = document.getElementById("machinePauseBtn")
  const machineStepBtn = document.getElementById("machineStepBtn")
  const machineResetBtn = document.getElementById("machineResetBtn")
  const machineSpeed = document.getElementById("machineSpeed")
  const trainSubmitBtn = document.getElementById("trainSubmitBtn")
  const trainingResetBtn = document.getElementById("trainingResetBtn")
  const evaluateCheckpointBtn = document.getElementById("evaluateCheckpointBtn")
  const jobList = document.getElementById("jobList")
  const jobLogViewer = document.getElementById("jobLogViewer")
  const timelineList = document.getElementById("timelineList")
  const timelineScrubber = document.getElementById("timelineScrubber")
  const timelinePlayBtn = document.getElementById("timelinePlayBtn")
  const timelinePauseBtn = document.getElementById("timelinePauseBtn")
  const timelineStatus = document.getElementById("timelineStatus")
  const holdButtons = Array.from(document.querySelectorAll(".hold-btn"))
  const tabButtons = Array.from(document.querySelectorAll("[data-tab]"))
  const tabPanels = Array.from(document.querySelectorAll("[data-panel]"))
  const configInputs = Array.from(document.querySelectorAll("[data-config-path]"))

  const model = {
    currentTab: "play",
    checkpoints: checkpointsSeed,
    jobs: jobsSeed,
    playSession: null,
    machineSession: null,
    machineRunning: false,
    machineTimer: null,
    humanTimer: null,
    humanBusy: false,
    axisInputs: [new Set(), new Set(), new Set()],
    selectedJobId: null,
    timeline: null,
    timelineSnapshot: null,
    timelineFrameIndex: 0,
    timelineTimer: null,
  }

  const keyMap = {
    KeyA: [0, -1],
    KeyD: [0, 1],
    KeyJ: [1, -1],
    KeyL: [1, 1],
    KeyW: [2, -1],
    KeyS: [2, 1],
  }

  function buildUrl(template, token, value) {
    return String(template || "").replace(token, encodeURIComponent(String(value)))
  }

  function fetchJson(url, options) {
    return fetch(url, {
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      ...(options || {}),
    }).then(async (response) => {
      const body = await response.json()
      if (!response.ok) {
        throw new Error(body.error || `request failed: ${response.status}`)
      }
      return body
    })
  }

  function setStageStatus(message) {
    stageStatus.textContent = message
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
      stageTitle.textContent = "Drive the arm with continuous shoulder, elbow, and grip control"
    } else if (mode === "machine") {
      stageEyebrow.textContent = "Machine Play"
      stageTitle.textContent = "Inspect a saved controller on the same grab-and-return task"
    } else {
      stageEyebrow.textContent = "Training Timeline"
      stageTitle.textContent = "Replay saved learning milestones from PPO training"
    }
  }

  function renderCards(container, entries) {
    container.innerHTML = entries
      .map(
        ([label, value]) => `
        <article class="state-card">
          <span class="metric-label">${label}</span>
          <strong>${value}</strong>
        </article>
      `
      )
      .join("")
  }

  function renderObservation(labels, values) {
    renderCards(
      observationGrid,
      labels.map((label, index) => [label, values && values[index] !== undefined ? values[index] : "-"])
    )
  }

  function renderRewardTerms(rewardTerms) {
    renderCards(
      rewardGrid,
      Object.entries(rewardTerms || {}).map(([label, value]) => [label, value])
    )
  }

  function updateGauges(action) {
    const values = Array.isArray(action) ? action : [0, 0, 0]
    gaugeValues.forEach((node, index) => {
      const value = Number(values[index] || 0)
      node.textContent = value.toFixed(2)
    })
    gaugeFills.forEach((node, index) => {
      const value = Math.max(-1, Math.min(1, Number(values[index] || 0)))
      const magnitude = Math.abs(value) * 50
      node.style.width = `${magnitude}%`
      node.style.left = value >= 0 ? "50%" : `${50 - magnitude}%`
      node.style.opacity = `${0.35 + Math.abs(value) * 0.65}`
    })
  }

  function drawPlaceholder() {
    ctx.clearRect(0, 0, stageCanvas.width, stageCanvas.height)
    const gradient = ctx.createLinearGradient(0, 0, 0, stageCanvas.height)
    gradient.addColorStop(0, "#09111d")
    gradient.addColorStop(1, "#101827")
    ctx.fillStyle = gradient
    ctx.fillRect(0, 0, stageCanvas.width, stageCanvas.height)
    ctx.fillStyle = "rgba(255,255,255,0.7)"
    ctx.font = "600 20px Space Grotesk"
    ctx.fillText("Create a Grabber session to begin.", 38, 44)
  }

  function worldToCanvas(scene, point) {
    const radius = Number(scene.world_radius || 1.45)
    const paddingX = 70
    const paddingY = 55
    const usableWidth = stageCanvas.width - paddingX * 2
    const usableHeight = stageCanvas.height - paddingY * 2
    const x = ((Number(point.x) + radius) / (radius * 2)) * usableWidth + paddingX
    const y = stageCanvas.height - ((((Number(point.y) + radius) / (radius * 2)) * usableHeight) + paddingY)
    return { x, y }
  }

  function drawScene(scene, action) {
    if (!scene) {
      drawPlaceholder()
      return
    }
    const gradient = ctx.createLinearGradient(0, 0, 0, stageCanvas.height)
    gradient.addColorStop(0, "#09111d")
    gradient.addColorStop(1, "#141c2a")
    ctx.fillStyle = gradient
    ctx.fillRect(0, 0, stageCanvas.width, stageCanvas.height)

    const home = worldToCanvas(scene, scene.home)
    const base = worldToCanvas(scene, scene.base)
    const shoulder = worldToCanvas(scene, scene.arm.shoulder_joint)
    const elbow = worldToCanvas(scene, scene.arm.elbow_joint)
    const fingertip = worldToCanvas(scene, scene.arm.fingertip)
    const coin = worldToCanvas(scene, scene.coin)
    const highlights = scene.highlights || {}

    const homeRadius = (Number(scene.home.radius || 0.18) / Number(scene.world_radius || 1.45)) * (stageCanvas.width * 0.5)
    ctx.save()
    ctx.strokeStyle = "rgba(230, 218, 135, 0.75)"
    ctx.lineWidth = 4
    ctx.setLineDash([10, 8])
    ctx.beginPath()
    ctx.arc(home.x, home.y, homeRadius, 0, Math.PI * 2)
    ctx.stroke()
    ctx.setLineDash([])
    ctx.fillStyle = "rgba(230, 218, 135, 0.12)"
    ctx.fillRect(home.x - homeRadius * 0.9, home.y + homeRadius * 0.4, homeRadius * 1.8, 12)
    ctx.restore()

    ctx.strokeStyle = `rgba(69, 219, 205, ${0.45 + (Number(highlights.shoulder || Math.abs(action[0] || 0)) * 0.55)})`
    ctx.lineWidth = 22
    ctx.lineCap = "round"
    ctx.beginPath()
    ctx.moveTo(base.x, base.y)
    ctx.lineTo(shoulder.x, shoulder.y)
    ctx.stroke()

    ctx.strokeStyle = `rgba(255, 122, 82, ${0.45 + (Number(highlights.elbow || Math.abs(action[1] || 0)) * 0.55)})`
    ctx.lineWidth = 18
    ctx.beginPath()
    ctx.moveTo(shoulder.x, shoulder.y)
    ctx.lineTo(elbow.x, elbow.y)
    ctx.stroke()

    ctx.strokeStyle = `rgba(235, 238, 244, ${0.45 + (Number(highlights.grip || Math.abs(action[2] || 0)) * 0.55)})`
    ctx.lineWidth = 10
    ctx.beginPath()
    ctx.moveTo(elbow.x, elbow.y)
    ctx.lineTo(fingertip.x, fingertip.y)
    ctx.stroke()

    const handDx = fingertip.x - elbow.x
    const handDy = fingertip.y - elbow.y
    const handLength = Math.hypot(handDx, handDy) || 1
    const normalX = -handDy / handLength
    const normalY = handDx / handLength
    const jawSpan = 6 + (Number(scene.arm.grip_open || 0) * 18)
    ctx.strokeStyle = "#f2f5f7"
    ctx.lineWidth = 4
    ctx.beginPath()
    ctx.moveTo(fingertip.x + normalX * jawSpan, fingertip.y + normalY * jawSpan)
    ctx.lineTo(fingertip.x + normalX * (jawSpan + 12), fingertip.y + normalY * (jawSpan + 12))
    ctx.moveTo(fingertip.x - normalX * jawSpan, fingertip.y - normalY * jawSpan)
    ctx.lineTo(fingertip.x - normalX * (jawSpan + 12), fingertip.y - normalY * (jawSpan + 12))
    ctx.stroke()

    ctx.fillStyle = "#cbd5de"
    ctx.beginPath()
    ctx.arc(base.x, base.y, 14, 0, Math.PI * 2)
    ctx.arc(shoulder.x, shoulder.y, 10, 0, Math.PI * 2)
    ctx.arc(elbow.x, elbow.y, 9, 0, Math.PI * 2)
    ctx.fill()

    ctx.save()
    ctx.shadowColor = scene.coin.held ? "rgba(255, 215, 80, 0.95)" : "rgba(255, 215, 80, 0.5)"
    ctx.shadowBlur = scene.coin.held ? 28 : 16
    ctx.fillStyle = "#f1c451"
    ctx.beginPath()
    ctx.arc(coin.x, coin.y, 13, 0, Math.PI * 2)
    ctx.fill()
    ctx.strokeStyle = "#f9e3a0"
    ctx.lineWidth = 3
    ctx.stroke()
    ctx.restore()
  }

  function renderFrame(payload) {
    const frame = {
      action: payload.action || [0, 0, 0],
      reward: payload.reward || 0,
      reward_terms: payload.reward_terms || {},
      score: payload.score || 0,
      held: payload.held || false,
      done: payload.done || false,
      done_reason: payload.done_reason || "running",
      step_index: payload.step_index || 0,
      observation: payload.observation || [],
      observation_labels: payload.observation_labels || [],
      scene: payload.scene || null,
    }
    drawScene(frame.scene, frame.action)
    updateGauges(frame.action)
    telemetryNodes.step_index.textContent = String(frame.step_index)
    telemetryNodes.reward.textContent = String(frame.reward)
    telemetryNodes.score.textContent = String(frame.score)
    telemetryNodes.held.textContent = String(frame.held)
    telemetryNodes.done.textContent = String(frame.done)
    telemetryNodes.done_reason.textContent = String(frame.done_reason)
    renderRewardTerms(frame.reward_terms)
    renderObservation(frame.observation_labels, frame.observation)
  }

  function updateCheckpointButtonsState() {
    const hasCheckpoints = model.checkpoints.length > 0
    checkpointSelect.disabled = !hasCheckpoints
    machineCreateBtn.disabled = !hasCheckpoints
    machineRunBtn.disabled = !hasCheckpoints
    machinePauseBtn.disabled = !hasCheckpoints
    machineStepBtn.disabled = !hasCheckpoints
    machineResetBtn.disabled = !hasCheckpoints
    evaluateCheckpointBtn.disabled = !hasCheckpoints
  }

  function renderCheckpoints() {
    checkpointSelect.innerHTML = ""
    model.checkpoints.forEach((checkpoint) => {
      const option = document.createElement("option")
      option.value = checkpoint.id
      let label = checkpoint.label
      if (checkpoint.featured) {
        label += " (Featured)"
      }
      option.textContent = label
      checkpointSelect.appendChild(option)
    })
    updateCheckpointButtonsState()
    if (model.checkpoints.length) {
      checkpointSelect.value = model.checkpoints[0].id
      updateCheckpointSummary()
    } else {
      checkpointSummary.textContent = "No Grabber checkpoints yet."
    }
  }

  function renderJobs() {
    if (!model.jobs.length) {
      jobList.innerHTML = '<p class="panel-note">No jobs yet.</p>'
      jobLogViewer.textContent = "No job selected."
      renderTimeline(null)
      return
    }
    if (!model.selectedJobId || !model.jobs.some((job) => job.id === model.selectedJobId)) {
      model.selectedJobId = model.jobs[0].id
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
      button.addEventListener("click", async () => {
        model.selectedJobId = Number(button.dataset.jobId)
        renderJobs()
        updateJobDetails()
        await refreshTimeline()
      })
    })
    updateJobDetails()
  }

  function updateJobDetails() {
    const job = model.jobs.find((item) => item.id === model.selectedJobId)
    if (!job) {
      jobLogViewer.textContent = "No job selected."
      return
    }
    const lines = [`job #${job.id} | ${job.kind} | ${job.status}`]
    if (job.summary) {
      lines.push("", "summary:", JSON.stringify(job.summary, null, 2))
    }
    if (job.timeline && job.timeline.count) {
      lines.push("", `timeline snapshots: ${job.timeline.count}`)
    }
    if (job.metrics_tail && job.metrics_tail.length) {
      lines.push("", "recent metrics:", JSON.stringify(job.metrics_tail, null, 2))
    }
    if (job.stdout_tail) {
      lines.push("", "stdout:", job.stdout_tail)
    }
    if (job.stderr_tail) {
      lines.push("", "stderr:", job.stderr_tail)
    }
    jobLogViewer.textContent = lines.join("\n")
  }

  function renderTimeline(timeline) {
    model.timeline = timeline
    const snapshots = timeline && Array.isArray(timeline.snapshots) ? timeline.snapshots : []
    if (!snapshots.length) {
      stopTimelineLoop()
      timelineList.innerHTML = '<p class="panel-note">No timeline snapshots yet.</p>'
      timelineStatus.textContent = "Choose a completed training job to inspect its timeline snapshots."
      timelineScrubber.max = "0"
      timelineScrubber.value = "0"
      model.timelineSnapshot = null
      return
    }
    timelineList.innerHTML = snapshots
      .map(
        (snapshot) => `
          <button class="job-chip" type="button" data-snapshot-id="${snapshot.id}">
            <strong>${snapshot.label}</strong>
            <span>return ${Number(snapshot.return || 0).toFixed(2)}</span>
            <span>${snapshot.success ? "success" : snapshot.done_reason}</span>
          </button>
        `
      )
      .join("")
    Array.from(timelineList.querySelectorAll("[data-snapshot-id]")).forEach((button) => {
      button.addEventListener("click", async () => {
        const snapshotId = button.dataset.snapshotId
        await loadTimelineSnapshot(snapshotId)
      })
    })
    timelineStatus.textContent = `${snapshots.length} snapshot${snapshots.length === 1 ? "" : "s"} saved for this job.`
  }

  async function refreshTimeline() {
    const selectedJob = model.jobs.find((job) => job.id === model.selectedJobId)
    if (!selectedJob || selectedJob.kind !== "train") {
      renderTimeline(null)
      return
    }
    const body = await fetchJson(buildUrl(urls.timeline, "999999", selectedJob.id))
    renderTimeline(body.timeline)
  }

  async function loadTimelineSnapshot(snapshotId) {
    if (!model.selectedJobId) {
      return
    }
    const base = buildUrl(urls.timelineSnapshot, "999999", model.selectedJobId)
    const body = await fetchJson(buildUrl(base, "SNAPSHOT_ID", snapshotId))
    model.timelineSnapshot = body.snapshot
    model.timelineFrameIndex = 0
    timelineScrubber.max = String(Math.max(0, (body.snapshot.rollout.frames || []).length - 1))
    timelineScrubber.value = "0"
    showTimelineFrame(0)
  }

  function showTimelineFrame(index) {
    if (!model.timelineSnapshot) {
      return
    }
    const frames = model.timelineSnapshot.rollout.frames || []
    if (!frames.length) {
      return
    }
    const bounded = Math.max(0, Math.min(index, frames.length - 1))
    model.timelineFrameIndex = bounded
    timelineScrubber.value = String(bounded)
    setStageMode("training")
    renderFrame(frames[bounded])
    timelineStatus.textContent =
      `${model.timelineSnapshot.label} | frame ${bounded + 1}/${frames.length} | ` +
      `return ${Number(model.timelineSnapshot.rollout.return || 0).toFixed(2)}`
  }

  function stopTimelineLoop() {
    window.clearTimeout(model.timelineTimer)
    model.timelineTimer = null
  }

  function scheduleTimelineLoop() {
    stopTimelineLoop()
    if (!model.timelineSnapshot) {
      return
    }
    model.timelineTimer = window.setTimeout(() => {
      const frames = model.timelineSnapshot.rollout.frames || []
      if (!frames.length) {
        return
      }
      const nextIndex = (model.timelineFrameIndex + 1) % frames.length
      showTimelineFrame(nextIndex)
      scheduleTimelineLoop()
    }, 180)
  }

  async function refreshCheckpoints() {
    const body = await fetchJson(urls.checkpoints)
    model.checkpoints = body.checkpoints
    renderCheckpoints()
  }

  async function refreshJobs() {
    const body = await fetchJson(urls.jobsList)
    model.jobs = body.jobs
    renderJobs()
    const hasRunning = model.jobs.some((job) => job.status === "running" || job.status === "queued")
    if (hasRunning) {
      runtimeStatus.textContent = "Runtime ready | job running"
    } else {
      runtimeStatus.textContent = "Runtime ready"
    }
    if (model.jobs.some((job) => job.status === "completed")) {
      await refreshCheckpoints()
    }
    await refreshTimeline().catch(() => null)
  }

  async function updateCheckpointSummary() {
    const selectedId = checkpointSelect.value
    if (!selectedId) {
      checkpointSummary.textContent = "No controller selected."
      return
    }
    try {
      const url = buildUrl(urls.checkpointSummary, "CHECKPOINT_ID", selectedId)
      const body = await fetchJson(url)
      const checkpoint = body.checkpoint
      const training = checkpoint.training_summary || {}
      const evaluation = checkpoint.evaluation_summary || {}
      const snapshot = checkpoint.timeline_snapshot || {}
      checkpointSummary.textContent =
        `Algorithm: ${training.algorithm || "ppo"} | ` +
        `Update: ${snapshot.update || training.updates_completed || training.update || "n/a"} | ` +
        `Eval success: ${evaluation.success_rate ?? "not evaluated"} | ` +
        `Mean return: ${evaluation.mean_return ?? snapshot.return ?? training.best_snapshot_return ?? "n/a"}`
    } catch (error) {
      checkpointSummary.textContent = error.message
    }
  }

  function createSession(controller, checkpointId) {
    const payload = { controller }
    if (checkpointId) {
      payload.checkpoint_id = checkpointId
    }
    return fetchJson(urls.createSession, {
      method: "POST",
      body: JSON.stringify(payload),
    })
  }

  function stepSession(sessionId, action) {
    const url = buildUrl(urls.stepSession, "SESSION_ID", sessionId)
    const payload = action === undefined ? {} : { action }
    return fetchJson(url, {
      method: "POST",
      body: JSON.stringify(payload),
    })
  }

  function resetSession(sessionId) {
    const url = buildUrl(urls.resetSession, "SESSION_ID", sessionId)
    return fetchJson(url, { method: "POST", body: "{}" })
  }

  function deleteSession(sessionId) {
    const url = buildUrl(urls.deleteSession, "SESSION_ID", sessionId)
    return fetchJson(url, { method: "DELETE" })
  }

  async function ensurePlaySession() {
    if (model.playSession) {
      return model.playSession
    }
    const payload = await createSession("human")
    model.playSession = payload.session.id
    renderFrame(payload)
    setStageStatus("Human session ready.")
    return model.playSession
  }

  async function ensureMachineSession() {
    if (model.machineSession) {
      return model.machineSession
    }
    const checkpointId = checkpointSelect.value
    const payload = await createSession("checkpoint", checkpointId)
    model.machineSession = payload.session.id
    renderFrame(payload)
    setStageStatus(`Machine session ready: ${checkpointId}.`)
    return model.machineSession
  }

  function composeHumanAction() {
    return model.axisInputs.map((entries) => {
      let total = 0
      entries.forEach((value) => {
        total += Number(value)
      })
      return Math.max(-1, Math.min(1, total))
    })
  }

  function stopHumanLoop() {
    window.clearTimeout(model.humanTimer)
    model.humanTimer = null
  }

  function hasActiveHumanInput() {
    return composeHumanAction().some((value) => Math.abs(value) > 0.0001)
  }

  async function runHumanStep() {
    if (model.humanBusy || !hasActiveHumanInput()) {
      return
    }
    model.humanBusy = true
    try {
      setStageMode("play")
      const sessionId = await ensurePlaySession()
      const payload = await stepSession(sessionId, composeHumanAction())
      renderFrame(payload)
      setStageStatus("Human control stepping.")
    } catch (error) {
      setStageStatus(error.message)
      stopHumanLoop()
    } finally {
      model.humanBusy = false
    }
  }

  function scheduleHumanLoop() {
    stopHumanLoop()
    if (!hasActiveHumanInput()) {
      return
    }
    model.humanTimer = window.setTimeout(async () => {
      await runHumanStep()
      scheduleHumanLoop()
    }, 95)
  }

  function stopMachineLoop() {
    model.machineRunning = false
    window.clearTimeout(model.machineTimer)
    model.machineTimer = null
  }

  async function runMachineStep() {
    if (!model.machineSession) {
      await ensureMachineSession()
    }
    const payload = await stepSession(model.machineSession)
    renderFrame(payload)
    if (payload.done || payload.truncated) {
      stopMachineLoop()
      setStageStatus("Machine session reached a terminal state.")
    }
  }

  function scheduleMachineLoop() {
    window.clearTimeout(model.machineTimer)
    if (!model.machineRunning) {
      return
    }
    const delay = Math.max(60, 560 - Number(machineSpeed.value) * 32)
    model.machineTimer = window.setTimeout(async () => {
      try {
        await runMachineStep()
      } catch (error) {
        stopMachineLoop()
        setStageStatus(error.message)
      }
      scheduleMachineLoop()
    }, delay)
  }

  function deepClone(value) {
    return JSON.parse(JSON.stringify(value))
  }

  function setNestedValue(target, path, value) {
    const parts = path.split(".")
    let current = target
    for (let index = 0; index < parts.length - 1; index += 1) {
      const part = parts[index]
      const nextIsIndex = /^\d+$/.test(parts[index + 1])
      if (current[part] === undefined) {
        current[part] = nextIsIndex ? [] : {}
      }
      current = current[part]
    }
    current[parts[parts.length - 1]] = value
  }

  function readTrainingConfig() {
    const config = deepClone(trainingDefaults)
    configInputs.forEach((input) => {
      const rawValue = input.value
      const value = rawValue.includes(".") ? Number(rawValue) : Number(rawValue)
      setNestedValue(config, input.dataset.configPath, value)
    })
    return config
  }

  function resetTrainingForm() {
    configInputs.forEach((input) => {
      const path = input.dataset.configPath.split(".")
      let value = trainingDefaults
      path.forEach((part) => {
        value = value[part]
      })
      input.value = value
    })
  }

  async function submitJob(kind, extra) {
    const body = await fetchJson(urls.jobs, {
      method: "POST",
      body: JSON.stringify({ kind, ...(extra || {}) }),
    })
    await refreshJobs()
    return body.job
  }

  holdButtons.forEach((button) => {
    const axis = Number(button.dataset.axis)
    const value = Number(button.dataset.value)
    const activate = (event) => {
      event.preventDefault()
      model.axisInputs[axis].add(String(value))
      scheduleHumanLoop()
    }
    const deactivate = (event) => {
      event.preventDefault()
      model.axisInputs[axis].delete(String(value))
      if (!hasActiveHumanInput()) {
        stopHumanLoop()
      }
    }
    button.addEventListener("pointerdown", activate)
    button.addEventListener("pointerup", deactivate)
    button.addEventListener("pointerleave", deactivate)
    button.addEventListener("pointercancel", deactivate)
  })

  document.addEventListener("keydown", (event) => {
    const mapping = keyMap[event.code]
    if (!mapping) {
      return
    }
    event.preventDefault()
    model.axisInputs[mapping[0]].add(String(mapping[1]))
    scheduleHumanLoop()
  })

  document.addEventListener("keyup", (event) => {
    const mapping = keyMap[event.code]
    if (!mapping) {
      return
    }
    event.preventDefault()
    model.axisInputs[mapping[0]].delete(String(mapping[1]))
    if (!hasActiveHumanInput()) {
      stopHumanLoop()
    }
  })

  playNewSessionBtn.addEventListener("click", async () => {
    stopHumanLoop()
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
      renderFrame(payload)
      setStageStatus("Human session reset.")
    } catch (error) {
      setStageStatus(error.message)
    }
  })

  machineCreateBtn.addEventListener("click", async () => {
    stopMachineLoop()
    if (model.machineSession) {
      await deleteSession(model.machineSession).catch(() => null)
      model.machineSession = null
    }
    try {
      setStageMode("machine")
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
      scheduleMachineLoop()
    } catch (error) {
      setStageStatus(error.message)
    }
  })

  machinePauseBtn.addEventListener("click", () => {
    stopMachineLoop()
    setStageStatus("Machine playback paused.")
  })

  machineStepBtn.addEventListener("click", async () => {
    try {
      setStageMode("machine")
      await runMachineStep()
    } catch (error) {
      setStageStatus(error.message)
    }
  })

  machineResetBtn.addEventListener("click", async () => {
    if (!model.machineSession) {
      return
    }
    try {
      const payload = await resetSession(model.machineSession)
      renderFrame(payload)
      setStageStatus("Machine session reset.")
    } catch (error) {
      setStageStatus(error.message)
    }
  })

  checkpointSelect.addEventListener("change", async () => {
    if (model.machineSession) {
      await deleteSession(model.machineSession).catch(() => null)
      model.machineSession = null
    }
    updateCheckpointSummary()
  })

  trainSubmitBtn.addEventListener("click", async () => {
    try {
      const job = await submitJob("train", { config: readTrainingConfig() })
      setStageMode("training")
      timelineStatus.textContent = `Training job #${job.id} submitted.`
    } catch (error) {
      setStageStatus(error.message)
    }
  })

  trainingResetBtn.addEventListener("click", () => {
    resetTrainingForm()
    timelineStatus.textContent = "Training controls reset to defaults."
  })

  evaluateCheckpointBtn.addEventListener("click", async () => {
    const checkpointId = checkpointSelect.value
    if (!checkpointId) {
      return
    }
    try {
      const job = await submitJob("evaluate", { checkpoint_id: checkpointId, params: { episodes: 20 } })
      timelineStatus.textContent = `Evaluation job #${job.id} submitted for ${checkpointId}.`
    } catch (error) {
      setStageStatus(error.message)
    }
  })

  timelineScrubber.addEventListener("input", () => {
    showTimelineFrame(Number(timelineScrubber.value))
  })

  timelinePlayBtn.addEventListener("click", () => {
    scheduleTimelineLoop()
  })

  timelinePauseBtn.addEventListener("click", () => {
    stopTimelineLoop()
  })

  tabButtons.forEach((button) => {
    button.addEventListener("click", () => setStageMode(button.dataset.tab))
  })

  drawPlaceholder()
  renderRewardTerms({})
  renderObservation([], [])
  renderCheckpoints()
  renderJobs()
  refreshTimeline().catch(() => null)
  window.setInterval(() => {
    refreshJobs().catch(() => null)
  }, 2500)
  setStageStatus("Create a session to begin.")
})()
