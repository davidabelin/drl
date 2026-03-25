(function () {
  const root = document.getElementById("foundations-demo")
  const seedNode = document.getElementById("foundations-demo-seed")
  if (!root || !seedNode) {
    return
  }

  const endpoint = root.dataset.endpoint
  const controls = {
    discount: root.querySelector('input[name="discount"]'),
    slip: root.querySelector('input[name="slip"]'),
    living_reward: root.querySelector('input[name="living_reward"]'),
  }
  const outputs = {
    discount: root.querySelector('[data-output="discount"]'),
    slip: root.querySelector('[data-output="slip"]'),
    living_reward: root.querySelector('[data-output="living_reward"]'),
  }
  const metricNodes = Object.fromEntries(
    Array.from(document.querySelectorAll("[data-metric]")).map((node) => [node.dataset.metric, node])
  )
  const storyHeadline = document.querySelector("[data-story-headline]")
  const storyBody = document.querySelector("[data-story-body]")
  const gridworld = document.querySelector("[data-gridworld]")
  const pathStrip = document.querySelector("[data-path]")
  const pathSummary = document.querySelector("[data-path-summary]")
  const presetButtons = Array.from(root.querySelectorAll("[data-preset]"))
  const seedPayload = JSON.parse(seedNode.textContent)

  function formatMetric(name, value) {
    if (name === "start_value") {
      return Number(value).toFixed(3)
    }
    if (name === "path_length_hint") {
      return `${value} moves`
    }
    return String(value)
  }

  function syncOutputs() {
    outputs.discount.textContent = Number(controls.discount.value).toFixed(2)
    outputs.slip.textContent = Number(controls.slip.value).toFixed(2)
    outputs.living_reward.textContent = Number(controls.living_reward.value).toFixed(2)
  }

  function readParams() {
    return {
      discount: Number(controls.discount.value),
      slip: Number(controls.slip.value),
      living_reward: Number(controls.living_reward.value),
    }
  }

  function tileTint(cell, value) {
    if (cell === "G") {
      return "linear-gradient(160deg, rgba(18, 110, 97, 0.30), rgba(255, 255, 255, 0.92))"
    }
    if (cell === "H") {
      return "linear-gradient(160deg, rgba(201, 101, 55, 0.28), rgba(255, 255, 255, 0.92))"
    }
    const ratio = Math.max(0, Math.min(1, (value + 1) / 2))
    const teal = Math.round(70 + ratio * 90)
    const orange = Math.round(140 - ratio * 55)
    return `linear-gradient(160deg, rgba(${orange}, ${teal}, 140, 0.20), rgba(255, 255, 255, 0.94))`
  }

  function renderGrid(payload) {
    const highlighted = new Set(payload.path_states)
    const pathOrder = new Map(payload.path_states.map((state, index) => [state, index]))
    gridworld.innerHTML = payload.grid
      .map((cell) => {
        const typeClass =
          cell.cell === "G" ? "goal" : cell.cell === "H" ? "hole" : cell.index === 0 ? "start" : "floor"
        const pathClass = highlighted.has(cell.index) ? " path-active" : ""
        const stepIndex = pathOrder.get(cell.index)
        const stepBadge =
          stepIndex === undefined
            ? ""
            : `<span class="path-step">${stepIndex === 0 ? "Start" : `Step ${stepIndex}`}</span>`
        const action = cell.best_action_arrow || cell.cell
        const caption =
          cell.cell === "G"
            ? "Goal"
            : cell.cell === "H"
              ? "Hole"
              : cell.index === 0
                ? "Start"
                : cell.best_action || "Terminal"

        return `
          <article class="grid-cell ${typeClass}${pathClass}" style="background:${tileTint(cell.cell, cell.value)}">
            <div class="grid-cell-head">
              <span class="tile-badge">${cell.cell}</span>
              <span class="arrow-badge">${action}</span>
            </div>
            ${stepBadge}
            <strong>${Number(cell.value).toFixed(3)}</strong>
            <span class="grid-caption">${caption}</span>
          </article>
        `
      })
      .join("")
  }

  function renderPath(payload) {
    const indexLookup = Object.fromEntries(payload.grid.map((cell) => [cell.index, cell]))
    const destination = indexLookup[payload.path_states[payload.path_states.length - 1]]
    const stepCount = Math.max(payload.path_states.length - 1, 0)
    const status =
      destination && destination.cell === "G"
        ? "The greedy path reaches the goal."
        : destination && destination.cell === "H"
          ? "The greedy path falls into a hole."
          : "The greedy path stalls or loops before reaching a terminal tile."

    const steps = payload.path.length
      ? payload.path.map((step) => `<span class="path-chip">${step}</span>`).join("")
      : '<span class="path-chip">Stay put</span>'

    pathStrip.innerHTML = `<span class="path-chip path-chip-start">Start</span>${steps}`
    pathSummary.textContent = `${status} Current trace length: ${stepCount} decisions.`
  }

  function render(payload) {
    storyHeadline.textContent = payload.story.headline
    storyBody.textContent = payload.story.body
    Object.entries(payload.metrics).forEach(([name, value]) => {
      if (metricNodes[name]) {
        metricNodes[name].textContent = formatMetric(name, value)
      }
    })
    renderGrid(payload)
    renderPath(payload)
  }

  async function refresh() {
    syncOutputs()
    const params = readParams()
    const search = new URLSearchParams({
      discount: params.discount.toFixed(2),
      slip: params.slip.toFixed(2),
      living_reward: params.living_reward.toFixed(2),
    })
    try {
      const response = await fetch(`${endpoint}?${search.toString()}`, {
        headers: { Accept: "application/json" },
      })
      if (!response.ok) {
        return
      }
      render(await response.json())
    } catch (error) {
      console.error("foundations demo refresh failed", error)
    }
  }

  let refreshTimer = null
  function scheduleRefresh() {
    syncOutputs()
    window.clearTimeout(refreshTimer)
    refreshTimer = window.setTimeout(refresh, 120)
  }

  Object.values(controls).forEach((input) => {
    input.addEventListener("input", scheduleRefresh)
    input.addEventListener("change", refresh)
  })

  presetButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const preset = JSON.parse(button.dataset.preset)
      controls.discount.value = String(preset.discount)
      controls.slip.value = String(preset.slip)
      controls.living_reward.value = String(preset.living_reward)
      refresh()
    })
  })

  syncOutputs()
  render(seedPayload)
})()
